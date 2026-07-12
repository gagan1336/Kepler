"""
ANTIGRAVITY — Stock Lookup Module
Powers the Stock Search feature:
  - Symbol search / autocomplete from a curated NSE index list
  - Live price data via yfinance
  - Fundamentals from Screener.in (existing fundamentals_fetcher)
  - Shareholding pattern (Promoter, FII, DII, Public)
  - FII/DII trend (QoQ change)
  - Company-specific news filtered from recent RSS cache
  - Rule-based Analyst Verdict (STRONG BUY / BUY / HOLD / AVOID)

In-memory cache: 4 hours per symbol.
"""
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import requests
import yfinance as yf
from loguru import logger

from fundamentals_fetcher import fetch_fundamentals
import stock_universe

# Load the complete NSE stock universe at startup (non-blocking via disk cache)
try:
    stock_universe.load_universe()
    logger.info(f"Stock universe ready: {stock_universe.universe_size()} stocks")
except Exception as _e:
    logger.warning(f"Stock universe load failed at startup: {_e}")


# ── In-memory cache ────────────────────────────────────────────────────────────
_stock_cache: Dict[str, Dict] = {}
_CACHE_TTL_SECONDS = 4 * 3600  # 4 hours

# ── Shared requests session with browser-like headers (avoids 429) ─────────────
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com/",
})


# ── NSE Master Stock List (Nifty 500 + popular mid/small caps) ─────────────────
POPULAR_STOCKS = [
    # ── Nifty 50 ─────────────────────────────────────────────────────────────
    {"symbol": "RELIANCE",    "name": "Reliance Industries",              "sector": "Energy"},
    {"symbol": "TCS",         "name": "Tata Consultancy Services",        "sector": "IT"},
    {"symbol": "HDFCBANK",    "name": "HDFC Bank",                        "sector": "Banking"},
    {"symbol": "BHARTIARTL",  "name": "Bharti Airtel",                    "sector": "Telecom"},
    {"symbol": "ICICIBANK",   "name": "ICICI Bank",                       "sector": "Banking"},
    {"symbol": "INFY",        "name": "Infosys",                          "sector": "IT"},
    {"symbol": "INFOSYS",     "name": "Infosys",                          "sector": "IT"},
    {"symbol": "SBIN",        "name": "State Bank of India",              "sector": "Banking"},
    {"symbol": "HINDUNILVR",  "name": "Hindustan Unilever",               "sector": "FMCG"},
    {"symbol": "ITC",         "name": "ITC Limited",                      "sector": "FMCG"},
    {"symbol": "KOTAKBANK",   "name": "Kotak Mahindra Bank",              "sector": "Banking"},
    {"symbol": "LT",          "name": "Larsen & Toubro",                  "sector": "Infrastructure"},
    {"symbol": "AXISBANK",    "name": "Axis Bank",                        "sector": "Banking"},
    {"symbol": "ASIANPAINT",  "name": "Asian Paints",                     "sector": "Paints"},
    {"symbol": "MARUTI",      "name": "Maruti Suzuki",                    "sector": "Auto"},
    {"symbol": "SUNPHARMA",   "name": "Sun Pharmaceutical Industries",    "sector": "Pharma"},
    {"symbol": "ULTRACEMCO",  "name": "UltraTech Cement",                 "sector": "Cement"},
    {"symbol": "BAJFINANCE",  "name": "Bajaj Finance",                    "sector": "NBFC"},
    {"symbol": "TITAN",       "name": "Titan Company",                    "sector": "Consumer"},
    {"symbol": "WIPRO",       "name": "Wipro",                            "sector": "IT"},
    {"symbol": "NESTLEIND",   "name": "Nestle India",                     "sector": "FMCG"},
    {"symbol": "TATAMOTORS",  "name": "Tata Motors",                      "sector": "Auto"},
    {"symbol": "TATASTEEL",   "name": "Tata Steel",                       "sector": "Metals"},
    {"symbol": "HCLTECH",     "name": "HCL Technologies",                 "sector": "IT"},
    {"symbol": "POWERGRID",   "name": "Power Grid Corporation",           "sector": "Utilities"},
    {"symbol": "NTPC",        "name": "NTPC Limited",                     "sector": "Utilities"},
    {"symbol": "COALINDIA",   "name": "Coal India",                       "sector": "Mining"},
    {"symbol": "ONGC",        "name": "Oil & Natural Gas Corporation",    "sector": "Energy"},
    {"symbol": "ADANIENT",    "name": "Adani Enterprises",                "sector": "Conglomerate"},
    {"symbol": "ADANIPORTS",  "name": "Adani Ports & SEZ",               "sector": "Infrastructure"},
    {"symbol": "JSWSTEEL",    "name": "JSW Steel",                        "sector": "Metals"},
    {"symbol": "BAJAJFINSV",  "name": "Bajaj Finserv",                    "sector": "Financial Services"},
    {"symbol": "HDFCLIFE",    "name": "HDFC Life Insurance",              "sector": "Insurance"},
    {"symbol": "SBILIFE",     "name": "SBI Life Insurance",               "sector": "Insurance"},
    {"symbol": "DIVISLAB",    "name": "Divi's Laboratories",              "sector": "Pharma"},
    {"symbol": "DRREDDY",     "name": "Dr. Reddy's Laboratories",         "sector": "Pharma"},
    {"symbol": "CIPLA",       "name": "Cipla",                            "sector": "Pharma"},
    {"symbol": "EICHERMOT",   "name": "Eicher Motors",                    "sector": "Auto"},
    {"symbol": "BAJAJ-AUTO",  "name": "Bajaj Auto",                       "sector": "Auto"},
    {"symbol": "HEROMOTOCO",  "name": "Hero MotoCorp",                    "sector": "Auto"},
    {"symbol": "GRASIM",      "name": "Grasim Industries",                "sector": "Diversified"},
    {"symbol": "INDUSINDBK",  "name": "IndusInd Bank",                    "sector": "Banking"},
    {"symbol": "TECHM",       "name": "Tech Mahindra",                    "sector": "IT"},
    {"symbol": "UPL",         "name": "UPL Limited",                      "sector": "Agrochemicals"},
    {"symbol": "APOLLOHOSP",  "name": "Apollo Hospitals Enterprise",      "sector": "Healthcare"},
    {"symbol": "TATACONSUM",  "name": "Tata Consumer Products",           "sector": "FMCG"},
    {"symbol": "M&M",         "name": "Mahindra & Mahindra",              "sector": "Auto"},
    {"symbol": "MM",          "name": "Mahindra & Mahindra",              "sector": "Auto"},
    {"symbol": "BRITANNIA",   "name": "Britannia Industries",             "sector": "FMCG"},
    # ── Nifty Next 50 ─────────────────────────────────────────────────────────
    {"symbol": "ADANIGREEN",  "name": "Adani Green Energy",               "sector": "Utilities"},
    {"symbol": "ADANIPOWER",  "name": "Adani Power",                      "sector": "Utilities"},
    {"symbol": "ATGL",        "name": "Adani Total Gas",                  "sector": "Utilities"},
    {"symbol": "AWL",         "name": "Adani Wilmar",                     "sector": "FMCG"},
    {"symbol": "AMBUJACEM",   "name": "Ambuja Cements",                   "sector": "Cement"},
    {"symbol": "ACC",         "name": "ACC Limited",                      "sector": "Cement"},
    {"symbol": "SHREECEM",    "name": "Shree Cement",                     "sector": "Cement"},
    {"symbol": "RAMCOCEM",    "name": "The Ramco Cements",                "sector": "Cement"},
    {"symbol": "JKCEMENT",    "name": "JK Cement",                        "sector": "Cement"},
    {"symbol": "DALMIACEM",   "name": "Dalmia Bharat",                    "sector": "Cement"},
    {"symbol": "TRENT",       "name": "Trent Limited",                    "sector": "Retail"},
    {"symbol": "DMART",       "name": "Avenue Supermarts (D-Mart)",       "sector": "Retail"},
    {"symbol": "PAGEIND",     "name": "Page Industries",                  "sector": "Textiles"},
    {"symbol": "ICICIPRULI",  "name": "ICICI Prudential Life Insurance",  "sector": "Insurance"},
    {"symbol": "ICICIGI",     "name": "ICICI Lombard General Insurance",  "sector": "Insurance"},
    {"symbol": "STARHEALTH",  "name": "Star Health & Allied Insurance",   "sector": "Insurance"},
    {"symbol": "NIACL",       "name": "New India Assurance",              "sector": "Insurance"},
    {"symbol": "LICI",        "name": "Life Insurance Corporation of India","sector": "Insurance"},
    {"symbol": "GODREJCP",    "name": "Godrej Consumer Products",         "sector": "FMCG"},
    {"symbol": "DABUR",       "name": "Dabur India",                      "sector": "FMCG"},
    {"symbol": "MARICO",      "name": "Marico",                           "sector": "FMCG"},
    {"symbol": "EMAMILTD",    "name": "Emami",                            "sector": "FMCG"},
    {"symbol": "COLPAL",      "name": "Colgate-Palmolive India",          "sector": "FMCG"},
    {"symbol": "PGHH",        "name": "Procter & Gamble Hygiene",         "sector": "FMCG"},
    {"symbol": "GILLETTE",    "name": "Gillette India",                   "sector": "FMCG"},
    {"symbol": "JUBLFOOD",    "name": "Jubilant Foodworks",               "sector": "Consumer"},
    {"symbol": "DEVYANI",     "name": "Devyani International",            "sector": "Consumer"},
    {"symbol": "WESTLIFE",    "name": "Westlife Foodworld",               "sector": "Consumer"},
    {"symbol": "BECTOR",      "name": "Mrs Bectors Food",                 "sector": "FMCG"},
    {"symbol": "TATAPOWER",   "name": "Tata Power",                       "sector": "Utilities"},
    {"symbol": "TORNTPOWER",  "name": "Torrent Power",                    "sector": "Utilities"},
    {"symbol": "CESC",        "name": "CESC Limited",                     "sector": "Utilities"},
    {"symbol": "NHPC",        "name": "NHPC Limited",                     "sector": "Utilities"},
    {"symbol": "SJVN",        "name": "SJVN Limited",                     "sector": "Utilities"},
    {"symbol": "RECLTD",      "name": "REC Limited",                      "sector": "Finance"},
    {"symbol": "PFC",         "name": "Power Finance Corporation",        "sector": "Finance"},
    {"symbol": "IRFC",        "name": "Indian Railway Finance Corp",      "sector": "Finance"},
    # ── Banking & Financial Services ──────────────────────────────────────────
    {"symbol": "BANKBARODA",  "name": "Bank of Baroda",                   "sector": "Banking"},
    {"symbol": "PNB",         "name": "Punjab National Bank",             "sector": "Banking"},
    {"symbol": "CANBK",       "name": "Canara Bank",                      "sector": "Banking"},
    {"symbol": "UNIONBANK",   "name": "Union Bank of India",              "sector": "Banking"},
    {"symbol": "CENTRALBK",   "name": "Central Bank of India",            "sector": "Banking"},
    {"symbol": "INDIANB",     "name": "Indian Bank",                      "sector": "Banking"},
    {"symbol": "IOB",         "name": "Indian Overseas Bank",             "sector": "Banking"},
    {"symbol": "MAHABANK",    "name": "Bank of Maharashtra",              "sector": "Banking"},
    {"symbol": "UCOBANK",     "name": "UCO Bank",                         "sector": "Banking"},
    {"symbol": "FEDERALBNK",  "name": "Federal Bank",                     "sector": "Banking"},
    {"symbol": "BANDHANBNK",  "name": "Bandhan Bank",                     "sector": "Banking"},
    {"symbol": "IDFCFIRSTB",  "name": "IDFC First Bank",                  "sector": "Banking"},
    {"symbol": "RBLBANK",     "name": "RBL Bank",                         "sector": "Banking"},
    {"symbol": "YESBANK",     "name": "Yes Bank",                         "sector": "Banking"},
    {"symbol": "KARURVYSYA",  "name": "Karur Vysya Bank",                 "sector": "Banking"},
    {"symbol": "SOUTHBANK",   "name": "South Indian Bank",                "sector": "Banking"},
    {"symbol": "CSBBANK",     "name": "CSB Bank",                         "sector": "Banking"},
    {"symbol": "UJJIVANSFB",  "name": "Ujjivan Small Finance Bank",       "sector": "Banking"},
    {"symbol": "ESAFSFB",     "name": "ESAF Small Finance Bank",          "sector": "Banking"},
    {"symbol": "EQUITASBNK",  "name": "Equitas Small Finance Bank",       "sector": "Banking"},
    {"symbol": "AUBANK",      "name": "AU Small Finance Bank",            "sector": "Banking"},
    {"symbol": "LICHSGFIN",   "name": "LIC Housing Finance",              "sector": "NBFC"},
    {"symbol": "CHOLAFIN",    "name": "Cholamandalam Investment & Finance","sector": "NBFC"},
    {"symbol": "MUTHOOTFIN",  "name": "Muthoot Finance",                  "sector": "NBFC"},
    {"symbol": "MANAPPURAM",  "name": "Manappuram Finance",               "sector": "NBFC"},
    {"symbol": "BAJAJHFL",    "name": "Bajaj Housing Finance",            "sector": "NBFC"},
    {"symbol": "PNBHOUSING",  "name": "PNB Housing Finance",              "sector": "NBFC"},
    {"symbol": "REPCO",       "name": "Repco Home Finance",               "sector": "NBFC"},
    {"symbol": "AAVAS",       "name": "Aavas Financiers",                 "sector": "NBFC"},
    {"symbol": "HOMEFIRST",   "name": "Home First Finance",               "sector": "NBFC"},
    {"symbol": "SUVENPHAR",   "name": "Suven Pharmaceuticals",            "sector": "Pharma"},
    {"symbol": "CAN_FIN_HOMES","name": "Can Fin Homes",                  "sector": "NBFC"},
    {"symbol": "SHRIRAMFIN",  "name": "Shriram Finance",                  "sector": "NBFC"},
    {"symbol": "MOTILALOFS",  "name": "Motilal Oswal Financial Services", "sector": "Broking"},
    {"symbol": "ANGELONE",    "name": "Angel One",                        "sector": "Broking"},
    {"symbol": "5PAISA",      "name": "5Paisa Capital",                   "sector": "Broking"},
    {"symbol": "IIFL",        "name": "IIFL Finance",                     "sector": "NBFC"},
    {"symbol": "JMFINANCIL",  "name": "JM Financial",                     "sector": "Financial Services"},
    {"symbol": "ISEC",        "name": "ICICI Securities",                 "sector": "Broking"},
    {"symbol": "HDFCAMC",     "name": "HDFC Asset Management Company",    "sector": "Asset Management"},
    {"symbol": "NIPPONLIFE",  "name": "Nippon Life India AMC",            "sector": "Asset Management"},
    {"symbol": "UTIAMC",      "name": "UTI Asset Management",             "sector": "Asset Management"},
    {"symbol": "360ONE",      "name": "360 ONE WAM",                      "sector": "Asset Management"},
    # ── IT & Technology ───────────────────────────────────────────────────────
    {"symbol": "LTIM",        "name": "LTIMindtree",                      "sector": "IT"},
    {"symbol": "MPHASIS",     "name": "Mphasis",                          "sector": "IT"},
    {"symbol": "PERSISTENT",  "name": "Persistent Systems",               "sector": "IT"},
    {"symbol": "COFORGE",     "name": "Coforge",                          "sector": "IT"},
    {"symbol": "HAPPSTMNDS",  "name": "Happiest Minds Technologies",      "sector": "IT"},
    {"symbol": "OFSS",        "name": "Oracle Financial Services Software","sector": "IT"},
    {"symbol": "KPIT",        "name": "KPIT Technologies",                "sector": "IT"},
    {"symbol": "TATAELXSI",   "name": "Tata Elxsi",                       "sector": "IT"},
    {"symbol": "BIRLASOFT",   "name": "Birlasoft",                        "sector": "IT"},
    {"symbol": "CYIENT",      "name": "Cyient",                           "sector": "IT"},
    {"symbol": "MASTEK",      "name": "Mastek",                           "sector": "IT"},
    {"symbol": "HEXAWARE",    "name": "Hexaware Technologies",            "sector": "IT"},
    {"symbol": "NIIT",        "name": "NIIT Limited",                     "sector": "IT"},
    {"symbol": "INTELLECT",   "name": "Intellect Design Arena",           "sector": "IT"},
    {"symbol": "RATEGAIN",    "name": "RateGain Travel Technologies",     "sector": "IT"},
    {"symbol": "ROUTE",       "name": "Route Mobile",                     "sector": "IT"},
    {"symbol": "TANLA",       "name": "Tanla Platforms",                  "sector": "IT"},
    {"symbol": "LATENTVIEW",  "name": "LatentView Analytics",             "sector": "IT"},
    {"symbol": "NEWGEN",      "name": "Newgen Software Technologies",     "sector": "IT"},
    {"symbol": "SONATSOFTW",  "name": "Sonata Software",                  "sector": "IT"},
    {"symbol": "BSOFT",       "name": "BHARAT Dynamics... Bahavan Soft",  "sector": "IT"},
    {"symbol": "RAMKY",       "name": "Ramky Infrastructure",             "sector": "IT"},
    # ── Consumer Tech & Internet ───────────────────────────────────────────────
    {"symbol": "ZOMATO",      "name": "Zomato",                           "sector": "Consumer Tech"},
    {"symbol": "PAYTM",       "name": "Paytm (One97 Communications)",     "sector": "Fintech"},
    {"symbol": "NYKAA",       "name": "Nykaa (FSN E-Commerce)",           "sector": "Consumer Tech"},
    {"symbol": "POLICYBZR",   "name": "PB Fintech (PolicyBazaar)",        "sector": "Fintech"},
    {"symbol": "EASEMYTRIP",  "name": "Easy Trip Planners",               "sector": "Consumer Tech"},
    {"symbol": "DELHIVERY",   "name": "Delhivery",                        "sector": "Logistics"},
    {"symbol": "IXIGO",       "name": "Le Travenues Technology (Ixigo)",  "sector": "Consumer Tech"},
    {"symbol": "SWIGGY",      "name": "Swiggy",                           "sector": "Consumer Tech"},
    # ── Pharma & Healthcare ────────────────────────────────────────────────────
    {"symbol": "LUPIN",       "name": "Lupin",                            "sector": "Pharma"},
    {"symbol": "AUROPHARMA",  "name": "Aurobindo Pharma",                 "sector": "Pharma"},
    {"symbol": "IPCALAB",     "name": "IPCA Laboratories",                "sector": "Pharma"},
    {"symbol": "ALKEM",       "name": "Alkem Laboratories",               "sector": "Pharma"},
    {"symbol": "TORNTPHARM",  "name": "Torrent Pharmaceuticals",          "sector": "Pharma"},
    {"symbol": "GLENMARK",    "name": "Glenmark Pharmaceuticals",         "sector": "Pharma"},
    {"symbol": "ZYDUSLIFE",   "name": "Zydus Lifesciences",               "sector": "Pharma"},
    {"symbol": "BIOCON",      "name": "Biocon",                           "sector": "Pharma"},
    {"symbol": "CADILAHC",    "name": "Cadila Healthcare (Zydus)",        "sector": "Pharma"},
    {"symbol": "PFIZER",      "name": "Pfizer India",                     "sector": "Pharma"},
    {"symbol": "ABBOTINDIA",  "name": "Abbott India",                     "sector": "Pharma"},
    {"symbol": "GRANULES",    "name": "Granules India",                   "sector": "Pharma"},
    {"symbol": "NATCOPHARM",  "name": "Natco Pharma",                     "sector": "Pharma"},
    {"symbol": "LAURUSLABS",  "name": "Laurus Labs",                      "sector": "Pharma"},
    {"symbol": "SOLARA",      "name": "Solara Active Pharma Sciences",    "sector": "Pharma"},
    {"symbol": "THYROCARE",   "name": "Thyrocare Technologies",           "sector": "Diagnostics"},
    {"symbol": "METROPOLIS",  "name": "Metropolis Healthcare",            "sector": "Diagnostics"},
    {"symbol": "DRLAURED",    "name": "Dr. Lal PathLabs",                 "sector": "Diagnostics"},
    {"symbol": "MAXHEALTH",   "name": "Max Healthcare Institute",         "sector": "Healthcare"},
    {"symbol": "FORTIS",      "name": "Fortis Healthcare",                "sector": "Healthcare"},
    {"symbol": "NARAYANA",    "name": "Narayana Hrudayalaya",             "sector": "Healthcare"},
    {"symbol": "RAINBOW",     "name": "Rainbow Children's Medicare",      "sector": "Healthcare"},
    {"symbol": "KIMS",        "name": "Krishna Institute of Medical Sciences","sector": "Healthcare"},
    {"symbol": "MEDANTA",     "name": "Global Health (Medanta)",          "sector": "Healthcare"},
    {"symbol": "SUVENPHAR",   "name": "Suven Pharmaceuticals",            "sector": "Pharma"},
    {"symbol": "JBCHEPHARM",  "name": "JB Chemicals & Pharmaceuticals",   "sector": "Pharma"},
    # ── Auto & Ancillaries ────────────────────────────────────────────────────
    {"symbol": "ASHOKLEY",    "name": "Ashok Leyland",                    "sector": "Auto"},
    {"symbol": "TVSMOTORS",   "name": "TVS Motor Company",                "sector": "Auto"},
    {"symbol": "MOTHERSON",   "name": "Samvardhana Motherson International","sector": "Auto Ancillary"},
    {"symbol": "BOSCHLTD",    "name": "Bosch India",                      "sector": "Auto Ancillary"},
    {"symbol": "BHARATFORG",  "name": "Bharat Forge",                     "sector": "Auto Ancillary"},
    {"symbol": "TIINDIA",     "name": "Tube Investments of India",        "sector": "Auto Ancillary"},
    {"symbol": "SUNDRMFAST",  "name": "Sundaram Fasteners",               "sector": "Auto Ancillary"},
    {"symbol": "MINDAIND",    "name": "Minda Industries",                 "sector": "Auto Ancillary"},
    {"symbol": "EXIDEIND",    "name": "Exide Industries",                 "sector": "Auto Ancillary"},
    {"symbol": "AMARAJABAT",  "name": "Amara Raja Energy & Mobility",     "sector": "Auto Ancillary"},
    {"symbol": "CRAFTSMAN",   "name": "Craftsman Automation",             "sector": "Auto Ancillary"},
    {"symbol": "SUPRAJIT",    "name": "Suprajit Engineering",             "sector": "Auto Ancillary"},
    {"symbol": "GABRIEL",     "name": "Gabriel India",                    "sector": "Auto Ancillary"},
    {"symbol": "FIEM",        "name": "FIEM Industries",                  "sector": "Auto Ancillary"},
    {"symbol": "TATAMTRDVR",  "name": "Tata Motors DVR",                  "sector": "Auto"},
    # ── Metals & Mining ────────────────────────────────────────────────────────
    {"symbol": "HINDALCO",    "name": "Hindalco Industries",              "sector": "Metals"},
    {"symbol": "VEDL",        "name": "Vedanta",                          "sector": "Metals"},
    {"symbol": "NMDC",        "name": "NMDC Limited",                     "sector": "Mining"},
    {"symbol": "SAIL",        "name": "Steel Authority of India",         "sector": "Metals"},
    {"symbol": "NATIONALUM",  "name": "National Aluminium Company",       "sector": "Metals"},
    {"symbol": "MOIL",        "name": "MOIL Limited",                     "sector": "Mining"},
    {"symbol": "RATNAMANI",   "name": "Ratnamani Metals & Tubes",         "sector": "Metals"},
    {"symbol": "APL",         "name": "APL Apollo Tubes",                 "sector": "Metals"},
    {"symbol": "HLEGLAS",     "name": "HLE Glascoat",                     "sector": "Metals"},
    {"symbol": "KALYANKJIL",  "name": "Kalyan Jewellers",                 "sector": "Gems & Jewellery"},
    {"symbol": "PCJEWELLER",  "name": "PC Jeweller",                      "sector": "Gems & Jewellery"},
    {"symbol": "RAJESHEXPO",  "name": "Rajesh Exports",                   "sector": "Gems & Jewellery"},
    # ── Oil, Gas & Chemicals ──────────────────────────────────────────────────
    {"symbol": "BPCL",        "name": "Bharat Petroleum Corporation",     "sector": "Energy"},
    {"symbol": "IOC",         "name": "Indian Oil Corporation",           "sector": "Energy"},
    {"symbol": "HPCL",        "name": "Hindustan Petroleum Corporation",  "sector": "Energy"},
    {"symbol": "GAIL",        "name": "GAIL India",                       "sector": "Energy"},
    {"symbol": "MGL",         "name": "Mahanagar Gas",                    "sector": "Utilities"},
    {"symbol": "IGL",         "name": "Indraprastha Gas",                 "sector": "Utilities"},
    {"symbol": "PETRONET",    "name": "Petronet LNG",                     "sector": "Energy"},
    {"symbol": "OIL",         "name": "Oil India",                        "sector": "Energy"},
    {"symbol": "MRPL",        "name": "Mangalore Refinery & Petrochemicals","sector": "Energy"},
    {"symbol": "AARTIIND",    "name": "Aarti Industries",                 "sector": "Chemicals"},
    {"symbol": "SRF",         "name": "SRF Limited",                      "sector": "Chemicals"},
    {"symbol": "DEEPAKNTR",   "name": "Deepak Nitrite",                   "sector": "Chemicals"},
    {"symbol": "NAVINFLUOR",  "name": "Navin Fluorine International",     "sector": "Chemicals"},
    {"symbol": "FLUOROCHEM",  "name": "Gujarat Fluorochemicals",          "sector": "Chemicals"},
    {"symbol": "ALKYLAMINE",  "name": "Alkyl Amines Chemicals",           "sector": "Chemicals"},
    {"symbol": "FINEORG",     "name": "Fine Organic Industries",          "sector": "Chemicals"},
    {"symbol": "CLEAN",       "name": "Clean Science & Technology",       "sector": "Chemicals"},
    {"symbol": "TATACHEM",    "name": "Tata Chemicals",                   "sector": "Chemicals"},
    {"symbol": "GHCL",        "name": "GHCL",                             "sector": "Chemicals"},
    {"symbol": "VINATIORG",   "name": "Vinati Organics",                  "sector": "Chemicals"},
    {"symbol": "NOCIL",       "name": "NOCIL",                            "sector": "Chemicals"},
    {"symbol": "PIDILITIND",  "name": "Pidilite Industries",              "sector": "Chemicals"},
    {"symbol": "BASF",        "name": "BASF India",                       "sector": "Chemicals"},
    {"symbol": "COROMANDEL",  "name": "Coromandel International",         "sector": "Agrochemicals"},
    {"symbol": "PIIND",       "name": "PI Industries",                    "sector": "Agrochemicals"},
    {"symbol": "DHANUKA",     "name": "Dhanuka Agritech",                  "sector": "Agrochemicals"},
    {"symbol": "SUMICHEM",    "name": "Sumitomo Chemical India",          "sector": "Agrochemicals"},
    {"symbol": "BAYER",       "name": "Bayer CropScience",                "sector": "Agrochemicals"},
    {"symbol": "RALLIS",      "name": "Rallis India",                     "sector": "Agrochemicals"},
    # ── Infrastructure & Capital Goods ────────────────────────────────────────
    {"symbol": "SIEMENS",     "name": "Siemens India",                    "sector": "Industrial"},
    {"symbol": "ABB",         "name": "ABB India",                        "sector": "Industrial"},
    {"symbol": "HAVELLS",     "name": "Havells India",                    "sector": "Electricals"},
    {"symbol": "POLYCAB",     "name": "Polycab India",                    "sector": "Electricals"},
    {"symbol": "KEI",         "name": "KEI Industries",                   "sector": "Electricals"},
    {"symbol": "CUMMINSIND",  "name": "Cummins India",                    "sector": "Industrial"},
    {"symbol": "THERMAX",     "name": "Thermax",                          "sector": "Industrial"},
    {"symbol": "BHEL",        "name": "Bharat Heavy Electricals",         "sector": "Industrial"},
    {"symbol": "GRINDWELL",   "name": "Grindwell Norton",                 "sector": "Industrial"},
    {"symbol": "SCHAEFFLER",  "name": "Schaeffler India",                 "sector": "Industrial"},
    {"symbol": "TIMKEN",      "name": "Timken India",                     "sector": "Industrial"},
    {"symbol": "SKFINDIA",    "name": "SKF India",                        "sector": "Industrial"},
    {"symbol": "ASAHIINDIA",  "name": "Asahi India Glass",                "sector": "Industrial"},
    {"symbol": "KNRCON",      "name": "KNR Constructions",                "sector": "Infrastructure"},
    {"symbol": "KALPATPOWR",  "name": "Kalpataru Projects International",  "sector": "Infrastructure"},
    {"symbol": "GMRAIRPORT",  "name": "GMR Airports Infrastructure",      "sector": "Infrastructure"},
    {"symbol": "IRB",         "name": "IRB Infrastructure Developers",    "sector": "Infrastructure"},
    {"symbol": "GPPL",        "name": "Gujarat Pipavav Port",             "sector": "Infrastructure"},
    {"symbol": "APLAPOLLO",   "name": "APL Apollo Tubes",                 "sector": "Metals"},
    {"symbol": "CONCOR",      "name": "Container Corporation of India",   "sector": "Logistics"},
    {"symbol": "TITAGARH",    "name": "Titagarh Rail Systems",            "sector": "Industrial"},
    # ── Defence ────────────────────────────────────────────────────────────────
    {"symbol": "HAL",         "name": "Hindustan Aeronautics Limited",    "sector": "Defence"},
    {"symbol": "BEL",         "name": "Bharat Electronics",               "sector": "Defence"},
    {"symbol": "SOLARINDS",   "name": "Solar Industries India",           "sector": "Defence"},
    {"symbol": "DATAPATTNS",  "name": "Data Patterns India",              "sector": "Defence"},
    {"symbol": "MAZDOCK",     "name": "Mazagon Dock Shipbuilders",        "sector": "Defence"},
    {"symbol": "GESHIP",      "name": "Garden Reach Shipbuilders",        "sector": "Defence"},
    {"symbol": "COCHINSHIP",  "name": "Cochin Shipyard",                  "sector": "Defence"},
    {"symbol": "PARAS",       "name": "Paras Defence and Space Technologies","sector": "Defence"},
    {"symbol": "DRDO",        "name": "DRDOSYS Technologies",             "sector": "Defence"},
    {"symbol": "BEML",        "name": "BEML Limited",                     "sector": "Defence"},
    {"symbol": "MTAR",        "name": "MTAR Technologies",                "sector": "Defence"},
    # ── Real Estate ────────────────────────────────────────────────────────────
    {"symbol": "DLF",         "name": "DLF Limited",                      "sector": "Real Estate"},
    {"symbol": "GODREJPROP",  "name": "Godrej Properties",                "sector": "Real Estate"},
    {"symbol": "PRESTIGE",    "name": "Prestige Estates Projects",        "sector": "Real Estate"},
    {"symbol": "OBEROIRLTY",  "name": "Oberoi Realty",                    "sector": "Real Estate"},
    {"symbol": "PHOENIXLTD",  "name": "The Phoenix Mills",                "sector": "Real Estate"},
    {"symbol": "SOBHA",       "name": "Sobha",                            "sector": "Real Estate"},
    {"symbol": "BRIGADE",     "name": "Brigade Enterprises",              "sector": "Real Estate"},
    {"symbol": "MAHLIFE",     "name": "Mahindra Lifespace Developers",    "sector": "Real Estate"},
    {"symbol": "KOLTEPATIL",  "name": "Kolte-Patil Developers",           "sector": "Real Estate"},
    {"symbol": "INDIABULHSGF","name": "Indiabulls Housing Finance",       "sector": "NBFC"},
    {"symbol": "NCLIND",      "name": "NCL Industries",                   "sector": "Real Estate"},
    # ── Consumer Durables & Electricals ───────────────────────────────────────
    {"symbol": "VOLTAS",      "name": "Voltas",                           "sector": "Consumer Durables"},
    {"symbol": "WHIRLPOOL",   "name": "Whirlpool of India",               "sector": "Consumer Durables"},
    {"symbol": "BLUESTARCO",  "name": "Blue Star",                        "sector": "Consumer Durables"},
    {"symbol": "CROMPTON",    "name": "Crompton Greaves Consumer Electricals","sector": "Consumer Durables"},
    {"symbol": "ORIENTELEC",  "name": "Orient Electric",                  "sector": "Consumer Durables"},
    {"symbol": "DIXON",       "name": "Dixon Technologies",               "sector": "Electronics"},
    {"symbol": "AMBER",       "name": "Amber Enterprises India",          "sector": "Electronics"},
    {"symbol": "KAYNES",      "name": "Kaynes Technology India",          "sector": "Electronics"},
    {"symbol": "SYRMA",       "name": "Syrma SGS Technology",             "sector": "Electronics"},
    {"symbol": "IDEAFORGE",   "name": "ideaForge Technology",             "sector": "Electronics"},
    {"symbol": "VGUARD",      "name": "V-Guard Industries",               "sector": "Consumer Durables"},
    {"symbol": "MIDHANI",     "name": "Mishra Dhatu Nigam",               "sector": "Metals"},
    # ── Logistics & Transport ─────────────────────────────────────────────────
    {"symbol": "IRCTC",       "name": "Indian Railway Catering & Tourism Corp","sector": "Tourism"},
    {"symbol": "INDIGO",      "name": "InterGlobe Aviation (IndiGo)",     "sector": "Aviation"},
    {"symbol": "SPICEJET",    "name": "SpiceJet",                         "sector": "Aviation"},
    {"symbol": "BLUEDART",    "name": "Blue Dart Express",                "sector": "Logistics"},
    {"symbol": "GATI",        "name": "Gati",                             "sector": "Logistics"},
    {"symbol": "MAHINDCIE",   "name": "Mahindra CIE Automotive",          "sector": "Auto Ancillary"},
    {"symbol": "ALLCARGO",    "name": "Allcargo Logistics",               "sector": "Logistics"},
    {"symbol": "MAHLOG",      "name": "Mahindra Logistics",               "sector": "Logistics"},
    {"symbol": "VRL",         "name": "VRL Logistics",                    "sector": "Logistics"},
    {"symbol": "SNOWMAN",     "name": "Snowman Logistics",                "sector": "Logistics"},
    {"symbol": "TCI",         "name": "Transport Corporation of India",   "sector": "Logistics"},
    {"symbol": "MAHSEAMLES",  "name": "Maharashtra Seamless",             "sector": "Metals"},
    # ── Paints, Pipes & Building Materials ────────────────────────────────────
    {"symbol": "BERGEPAINT",  "name": "Berger Paints India",              "sector": "Paints"},
    {"symbol": "KANSAINER",   "name": "Kansai Nerolac Paints",            "sector": "Paints"},
    {"symbol": "INDIGO",      "name": "Indigo Paints",                    "sector": "Paints"},
    {"symbol": "AKZONOBEL",   "name": "Akzo Nobel India",                 "sector": "Paints"},
    {"symbol": "ASTRAL",      "name": "Astral Limited",                   "sector": "Pipes"},
    {"symbol": "SUPREMEIND",  "name": "Supreme Industries",               "sector": "Plastics"},
    {"symbol": "FINOLEX",     "name": "Finolex Industries",               "sector": "Pipes"},
    {"symbol": "PRINCEPIPE",  "name": "Prince Pipes & Fittings",          "sector": "Pipes"},
    {"symbol": "HINDZINC",    "name": "Hindustan Zinc",                   "sector": "Metals"},
    # ── Textiles & Apparel ────────────────────────────────────────────────────
    {"symbol": "GOKEX",       "name": "Gokaldas Exports",                 "sector": "Textiles"},
    {"symbol": "TRIDENT",     "name": "Trident",                          "sector": "Textiles"},
    {"symbol": "RUPA",        "name": "Rupa & Company",                   "sector": "Textiles"},
    {"symbol": "NUVAMA",      "name": "Nuvama Wealth Management",         "sector": "Financial Services"},
    {"symbol": "NILAINFO",    "name": "Nila Infrastructures",             "sector": "Infrastructure"},
    # ── Miscellaneous Popular ─────────────────────────────────────────────────
    {"symbol": "PIDILITIND",  "name": "Pidilite Industries",              "sector": "Chemicals"},
    {"symbol": "MCDOWELL-N",  "name": "United Spirits",                   "sector": "FMCG"},
    {"symbol": "RADICO",      "name": "Radico Khaitan",                   "sector": "FMCG"},
    {"symbol": "SULA",        "name": "Sula Vineyards",                   "sector": "FMCG"},
    {"symbol": "UNITDSPR",    "name": "United Spirits",                   "sector": "FMCG"},
    {"symbol": "INDIANHUME",  "name": "Indian Hume Pipe Company",         "sector": "Infrastructure"},
    {"symbol": "INDIGRID",    "name": "India Grid Trust",                 "sector": "Utilities"},
    {"symbol": "POWERINDIA",  "name": "Hitachi Energy India",             "sector": "Industrial"},
    {"symbol": "SUNTV",       "name": "Sun TV Network",                   "sector": "Media"},
    {"symbol": "ZEEL",        "name": "Zee Entertainment Enterprises",    "sector": "Media"},
    {"symbol": "NETWORK18",   "name": "Network18 Media & Investments",    "sector": "Media"},
    {"symbol": "TV18BRDCST",  "name": "TV18 Broadcast",                   "sector": "Media"},
    {"symbol": "DISHTV",      "name": "Dish TV India",                    "sector": "Media"},
    {"symbol": "HATHWAY",     "name": "Hathway Cable & Datacom",          "sector": "Telecom"},
    {"symbol": "INDUSTOWER",  "name": "Indus Towers",                     "sector": "Telecom"},
    {"symbol": "TATACOMM",    "name": "Tata Communications",              "sector": "Telecom"},
    {"symbol": "HFCL",        "name": "HFCL",                            "sector": "Telecom"},
    {"symbol": "RAILTEL",     "name": "RailTel Corporation of India",     "sector": "Telecom"},
    {"symbol": "ITI",         "name": "ITI Limited",                      "sector": "Telecom"},
    {"symbol": "TTML",        "name": "Tata Teleservices (Maharashtra)",  "sector": "Telecom"},
    {"symbol": "MCX",         "name": "Multi Commodity Exchange of India","sector": "Financial Services"},
    {"symbol": "BSE",         "name": "BSE Limited",                      "sector": "Financial Services"},
    {"symbol": "CAMS",        "name": "Computer Age Management Services",  "sector": "Financial Services"},
    {"symbol": "CDSL",        "name": "Central Depository Services India","sector": "Financial Services"},
    {"symbol": "NSDL",        "name": "NSDL",                             "sector": "Financial Services"},
    {"symbol": "NSLNISP",     "name": "NMDC Steel",                       "sector": "Metals"},
    {"symbol": "NHPC",        "name": "NHPC Limited",                     "sector": "Utilities"},
    {"symbol": "RVNL",        "name": "Rail Vikas Nigam",                 "sector": "Infrastructure"},
    {"symbol": "RITES",       "name": "RITES Limited",                    "sector": "Infrastructure"},
    {"symbol": "IRCON",       "name": "IRCON International",              "sector": "Infrastructure"},
    {"symbol": "NBCC",        "name": "NBCC (India)",                     "sector": "Infrastructure"},
    {"symbol": "HUDCO",       "name": "Housing & Urban Development Corporation","sector": "Finance"},
    {"symbol": "NLC",         "name": "NLC India",                        "sector": "Utilities"},
    {"symbol": "NLCINDIA",    "name": "NLC India",                        "sector": "Utilities"},
    {"symbol": "NALCO",       "name": "National Aluminium Company",       "sector": "Metals"},
    {"symbol": "ONGCINDIA",   "name": "Oil & Natural Gas Corporation",    "sector": "Energy"},
    {"symbol": "KPITTECH",    "name": "KPIT Technologies",                "sector": "IT"},
    {"symbol": "ZENSARTECH",  "name": "Zensar Technologies",              "sector": "IT"},
    {"symbol": "INFOEDGE",    "name": "Info Edge India (Naukri)",         "sector": "Consumer Tech"},
    {"symbol": "JUSTDIAL",    "name": "Just Dial",                        "sector": "Consumer Tech"},
    {"symbol": "CARTRADE",    "name": "CarTrade Tech",                    "sector": "Consumer Tech"},
    {"symbol": "INDIAMART",   "name": "IndiaMART InterMESH",              "sector": "Consumer Tech"},
    {"symbol": "NAUKRI",      "name": "Info Edge India",                  "sector": "Consumer Tech"},
    # ── Swing Trading Mid Caps (NSE F&O eligible) ────────────────────────────
    {"symbol": "ATUL",        "name": "Atul Limited",                     "sector": "Chemicals"},
    {"symbol": "BALRAMCHIN",  "name": "Balrampur Chini Mills",             "sector": "Sugar"},
    {"symbol": "RENUKA",      "name": "Shree Renuka Sugars",               "sector": "Sugar"},
    {"symbol": "DHAMPUR",     "name": "Dhampur Sugar Mills",               "sector": "Sugar"},
    {"symbol": "TRIVENI",     "name": "Triveni Engineering & Industries",  "sector": "Sugar"},
    {"symbol": "BAJAJCON",    "name": "Bajaj Consumer Care",               "sector": "FMCG"},
    {"symbol": "VBL",         "name": "Varun Beverages",                   "sector": "Beverages"},
    {"symbol": "HATSUN",      "name": "Hatsun Agro Products",              "sector": "Food"},
    {"symbol": "HERITAGE",    "name": "Heritage Foods",                    "sector": "Food"},
    {"symbol": "PRABHAT",     "name": "Prabhat Dairy",                     "sector": "Food"},
    {"symbol": "AVANTIFEED",  "name": "Avanti Feeds",                      "sector": "Food"},
    {"symbol": "ZYDUSWELL",   "name": "Zydus Wellness",                    "sector": "FMCG"},
    {"symbol": "JYOTHYLAB",   "name": "Jyothy Labs",                       "sector": "FMCG"},
    {"symbol": "GILLETTE",    "name": "Gillette India",                    "sector": "FMCG"},
    {"symbol": "HONAUT",      "name": "Honeywell Automation India",        "sector": "Industrial"},
    {"symbol": "3MINDIA",     "name": "3M India",                          "sector": "Industrial"},
    {"symbol": "ASTERDM",     "name": "Aster DM Healthcare",               "sector": "Healthcare"},
    {"symbol": "HEALTHIUM",   "name": "Healthium Medtech",                 "sector": "Healthcare"},
    {"symbol": "NUVOCO",      "name": "Nuvoco Vistas Corporation",         "sector": "Cement"},
    {"symbol": "HEIDELBERG",  "name": "HeidelbergCement India",            "sector": "Cement"},
    {"symbol": "BIRLACORP",   "name": "Birla Corporation",                 "sector": "Cement"},
    {"symbol": "SAGAR",       "name": "Sagar Cements",                     "sector": "Cement"},
    {"symbol": "ORIENTCEM",   "name": "Orient Cement",                     "sector": "Cement"},
    {"symbol": "PRSMJOHNSN",  "name": "Prism Johnson",                     "sector": "Cement"},
    {"symbol": "INDIACEM",    "name": "The India Cements",                 "sector": "Cement"},
    {"symbol": "SPENCERS",    "name": "Spencer's Retail",                  "sector": "Retail"},
    {"symbol": "VMART",       "name": "V-Mart Retail",                     "sector": "Retail"},
    {"symbol": "SHOPERSTOP",  "name": "Shoppers Stop",                     "sector": "Retail"},
    {"symbol": "ARVIND",      "name": "Arvind Limited",                    "sector": "Textiles"},
    {"symbol": "RAYMOND",     "name": "Raymond",                           "sector": "Textiles"},
    {"symbol": "KPR",         "name": "KPR Mill",                          "sector": "Textiles"},
    {"symbol": "WELSPUNIND",  "name": "Welspun India",                     "sector": "Textiles"},
    {"symbol": "VARDHMAN",    "name": "Vardhman Textiles",                 "sector": "Textiles"},
    {"symbol": "ALOK",        "name": "Alok Industries",                   "sector": "Textiles"},
    {"symbol": "HIMATSEIDE",  "name": "Himatsingka Seide",                 "sector": "Textiles"},
    {"symbol": "NIITLTD",     "name": "NIIT Limited",                      "sector": "Education"},
    {"symbol": "CARERATING",  "name": "CARE Ratings",                      "sector": "Financial Services"},
    {"symbol": "ICRA",        "name": "ICRA Limited",                      "sector": "Financial Services"},
    {"symbol": "CRISIL",      "name": "CRISIL Limited",                    "sector": "Financial Services"},
    {"symbol": "INFIBEAM",    "name": "Infibeam Avenues",                  "sector": "Fintech"},
    {"symbol": "PAYMATE",     "name": "PayMate India",                     "sector": "Fintech"},
    {"symbol": "ZAGGLE",      "name": "Zaggle Prepaid Ocean Services",     "sector": "Fintech"},
    {"symbol": "ONEPOINT",    "name": "One Point One Solutions",           "sector": "IT"},
    {"symbol": "XCHANGING",   "name": "Xchanging Solutions",               "sector": "IT"},
    {"symbol": "NUCLEUS",     "name": "Nucleus Software Exports",          "sector": "IT"},
    {"symbol": "SAKSOFT",     "name": "Saksoft",                           "sector": "IT"},
    {"symbol": "KRSNAA",      "name": "Krsnaa Diagnostics",                "sector": "Diagnostics"},
    {"symbol": "VIJAYA",      "name": "Vijaya Diagnostic Centre",          "sector": "Diagnostics"},
    {"symbol": "IIFLSEC",     "name": "IIFL Securities",                   "sector": "Broking"},
    {"symbol": "EMKAY",       "name": "Emkay Global Financial Services",   "sector": "Broking"},
    {"symbol": "GEOJITFSL",   "name": "Geojit Financial Services",         "sector": "Broking"},
    {"symbol": "HDFCSEC",     "name": "HDFC Securities",                   "sector": "Broking"},
    {"symbol": "DHANI",       "name": "Dhani Services",                    "sector": "Fintech"},
    {"symbol": "LORENTZSYS",  "name": "Lorenz Systems (Olx)",             "sector": "Consumer Tech"},
    # ── NSE Midcap 150 additions ──────────────────────────────────────────────
    {"symbol": "AIAENG",      "name": "AIA Engineering",                   "sector": "Industrial"},
    {"symbol": "CERA",        "name": "Cera Sanitaryware",                 "sector": "Consumer Durables"},
    {"symbol": "CEATLTD",     "name": "CEAT",                              "sector": "Auto Ancillary"},
    {"symbol": "MRF",         "name": "MRF Limited",                       "sector": "Auto Ancillary"},
    {"symbol": "APOLLOTYRE",  "name": "Apollo Tyres",                      "sector": "Auto Ancillary"},
    {"symbol": "BALKRISIND",  "name": "Balkrishna Industries",             "sector": "Auto Ancillary"},
    {"symbol": "JKTYRE",      "name": "JK Tyre & Industries",              "sector": "Auto Ancillary"},
    {"symbol": "TVSHLTD",     "name": "TVS Holdings",                      "sector": "Diversified"},
    {"symbol": "COCHINSHIP",  "name": "Cochin Shipyard",                   "sector": "Defence"},
    {"symbol": "FACT",        "name": "Fertilisers and Chemicals Travancore","sector": "Chemicals"},
    {"symbol": "GNFC",        "name": "Gujarat Narmada Valley Fertilizers","sector": "Chemicals"},
    {"symbol": "GSFC",        "name": "Gujarat State Fertilizers",         "sector": "Chemicals"},
    {"symbol": "NFL",         "name": "National Fertilizers",              "sector": "Chemicals"},
    {"symbol": "RCFLTD",      "name": "Rashtriya Chemicals & Fertilizers", "sector": "Chemicals"},
    {"symbol": "CHAMBAL",     "name": "Chambal Fertilizers",               "sector": "Chemicals"},
    {"symbol": "DEEPAK",      "name": "Deepak Fertilisers",                "sector": "Chemicals"},
    {"symbol": "GODREJAGRO",  "name": "Godrej Agrovet",                    "sector": "Agrochemicals"},
    {"symbol": "VSTTILLERS",  "name": "VST Tillers Tractors",              "sector": "Auto"},
    {"symbol": "ESCORTS",     "name": "Escorts Kubota",                    "sector": "Auto"},
    {"symbol": "SONACOMS",    "name": "Sona BLW Precision Forgings",       "sector": "Auto Ancillary"},
    {"symbol": "MAYURUNIQ",   "name": "Mayur Uniquoters",                  "sector": "Auto Ancillary"},
    {"symbol": "JWL",         "name": "Jupiter Wagons",                    "sector": "Industrial"},
    {"symbol": "RAILSYS",     "name": "Rail Vikas Nigam",                  "sector": "Infrastructure"},
    {"symbol": "IRSDCL",      "name": "IRSDCL",                            "sector": "Infrastructure"},
    {"symbol": "JPASSOCIAT",  "name": "Jaiprakash Associates",             "sector": "Infrastructure"},
    {"symbol": "NBCCLTD",     "name": "NBCC (India)",                      "sector": "Infrastructure"},
    {"symbol": "PNCINFRA",    "name": "PNC Infratech",                     "sector": "Infrastructure"},
    {"symbol": "SADBHAV",     "name": "Sadbhav Engineering",               "sector": "Infrastructure"},
    {"symbol": "HG",          "name": "HG Infra Engineering",              "sector": "Infrastructure"},
    {"symbol": "HGINFRA",     "name": "HG Infra Engineering",              "sector": "Infrastructure"},
    {"symbol": "POLYPLEX",    "name": "Polyplex Corporation",              "sector": "Chemicals"},
    {"symbol": "UFLEX",       "name": "UFLEX",                             "sector": "Packaging"},
    {"symbol": "ESTER",       "name": "Ester Industries",                  "sector": "Chemicals"},
    {"symbol": "HUHTAMAKI",   "name": "Huhtamaki India",                   "sector": "Packaging"},
    {"symbol": "TNPL",        "name": "Tamil Nadu Newsprint and Papers",   "sector": "Paper"},
    {"symbol": "ANDHRAPET",   "name": "Andhra Petrochemicals",             "sector": "Chemicals"},
    {"symbol": "PCBL",        "name": "Phillips Carbon Black",             "sector": "Chemicals"},
    {"symbol": "SUDARSCHEM",  "name": "Sudarshan Chemical Industries",     "sector": "Chemicals"},
    {"symbol": "ROSSARI",     "name": "Rossari Biotech",                   "sector": "Chemicals"},
    {"symbol": "HEMIPROP",    "name": "Hemisphere Properties",             "sector": "Real Estate"},
    {"symbol": "SUNTECKRLTY","name": "Sunteck Realty",                    "sector": "Real Estate"},
    {"symbol": "MACROTECH",   "name": "Macrotech Developers (Lodha)",     "sector": "Real Estate"},
    {"symbol": "GODREJPROP",  "name": "Godrej Properties",                 "sector": "Real Estate"},
    {"symbol": "ANANTRAJ",    "name": "Anant Raj",                         "sector": "Real Estate"},
    {"symbol": "RUSTOMJEE",   "name": "Keystone Realtors (Rustomjee)",    "sector": "Real Estate"},
    {"symbol": "SIGNATURE",   "name": "Signature Global (India)",          "sector": "Real Estate"},
    {"symbol": "MAHABANK",    "name": "Bank of Maharashtra",               "sector": "Banking"},
    {"symbol": "DCBBANK",     "name": "DCB Bank",                          "sector": "Banking"},
    {"symbol": "LAXMI",       "name": "Laxmi Finance & Investment",        "sector": "NBFC"},
    {"symbol": "FINOLEXCAB",  "name": "Finolex Cables",                    "sector": "Electricals"},
    {"symbol": "HINDCOPPER",  "name": "Hindustan Copper",                  "sector": "Metals"},
    {"symbol": "WELCORP",     "name": "Welspun Corp",                      "sector": "Metals"},
    {"symbol": "JINDALSAW",   "name": "Jindal SAW",                        "sector": "Metals"},
    {"symbol": "JSL",         "name": "Jindal Stainless",                  "sector": "Metals"},
    {"symbol": "JSLHISAR",    "name": "Jindal Stainless (Hisar)",          "sector": "Metals"},
    {"symbol": "NBVENTURES",  "name": "Nava Bharat Ventures",              "sector": "Metals"},
    {"symbol": "ELECTROSTE",  "name": "Electrosteel Castings",             "sector": "Metals"},
    {"symbol": "ISMT",        "name": "ISMT Limited",                      "sector": "Metals"},
    {"symbol": "MANGLI",      "name": "Man Industries (India)",            "sector": "Metals"},
    {"symbol": "SSWL",        "name": "Steel Strips Wheels",               "sector": "Auto Ancillary"},
    {"symbol": "ENDURANCE",   "name": "Endurance Technologies",            "sector": "Auto Ancillary"},
    {"symbol": "RANE",        "name": "Rane Holdings",                     "sector": "Auto Ancillary"},
    {"symbol": "RANEHOLDIN",  "name": "Rane Holdings",                     "sector": "Auto Ancillary"},
    {"symbol": "JAI",         "name": "Jai Corp",                          "sector": "Diversified"},
    {"symbol": "GHCLTEXTIL",  "name": "GHCL Textiles",                     "sector": "Textiles"},
    {"symbol": "SPORTKING",   "name": "Sportking India",                   "sector": "Textiles"},
    {"symbol": "PASUPATI",    "name": "Pasupati Acrylon",                  "sector": "Textiles"},
    {"symbol": "ZUARI",       "name": "Zuari Agro Chemicals",              "sector": "Chemicals"},
    {"symbol": "TORNTPHARM",  "name": "Torrent Pharmaceuticals",           "sector": "Pharma"},
    {"symbol": "CAPLIPOINT",  "name": "Caplin Point Laboratories",        "sector": "Pharma"},
    {"symbol": "STELLARIS",   "name": "Stellaris World Resources",         "sector": "Pharma"},
    {"symbol": "SUVEN",       "name": "Suven Life Sciences",               "sector": "Pharma"},
    {"symbol": "ANURAS",      "name": "Anuras Pharma",                     "sector": "Pharma"},
    {"symbol": "DIVIS",       "name": "Divi's Laboratories",               "sector": "Pharma"},
    {"symbol": "MARKSANS",    "name": "Marksans Pharma",                   "sector": "Pharma"},
    {"symbol": "PANACEA",     "name": "Panacea Biotec",                    "sector": "Pharma"},
    {"symbol": "HIKAL",       "name": "Hikal Limited",                     "sector": "Chemicals"},
    {"symbol": "SEQUENT",     "name": "SeQuent Scientific",                "sector": "Pharma"},
    {"symbol": "RPSGVENT",    "name": "RPSG Ventures",                     "sector": "Diversified"},
    {"symbol": "CCCL",        "name": "Consolidated Construction",          "sector": "Infrastructure"},
    {"symbol": "ELPRO",       "name": "Elpro International",               "sector": "Industrial"},
    {"symbol": "TEXRAIL",     "name": "Texmaco Rail & Engineering",        "sector": "Industrial"},
    {"symbol": "JTLIND",      "name": "JTL Industries",                    "sector": "Metals"},
    # ── NSE Smallcap 250 & swing trading favourites ───────────────────────────
    {"symbol": "TIPSINDLTD",  "name": "TIPS Industries",                   "sector": "Media"},
    {"symbol": "PVR",         "name": "PVR INOX",                          "sector": "Entertainment"},
    {"symbol": "INOXLEISUR",  "name": "INOX Leisure",                      "sector": "Entertainment"},
    {"symbol": "NAZARA",      "name": "Nazara Technologies",               "sector": "Gaming"},
    {"symbol": "NXTDIGITAL",  "name": "NXTDIGITAL",                        "sector": "Telecom"},
    {"symbol": "DELTACORP",   "name": "Delta Corp",                        "sector": "Entertainment"},
    {"symbol": "WONDERLA",    "name": "Wonderla Holidays",                 "sector": "Entertainment"},
    {"symbol": "MHRIL",       "name": "Mahindra Holidays & Resorts",       "sector": "Tourism"},
    {"symbol": "THOMASCOOK",  "name": "Thomas Cook (India)",               "sector": "Tourism"},
    {"symbol": "COX&KINGS",   "name": "Cox & Kings",                       "sector": "Tourism"},
    {"symbol": "LEMONTREE",   "name": "Lemon Tree Hotels",                 "sector": "Hospitality"},
    {"symbol": "CHALET",      "name": "Chalet Hotels",                     "sector": "Hospitality"},
    {"symbol": "IHCLTD",      "name": "Indian Hotels Company",             "sector": "Hospitality"},
    {"symbol": "EIHOTEL",     "name": "EIH Limited (Oberoi Hotels)",       "sector": "Hospitality"},
    {"symbol": "TAJGVK",      "name": "Taj GVK Hotels",                    "sector": "Hospitality"},
    {"symbol": "ABAN",        "name": "Aban Offshore",                     "sector": "Energy"},
    {"symbol": "SEAMECLTD",   "name": "Seamec",                            "sector": "Energy"},
    {"symbol": "AEGISLOG",    "name": "Aegis Logistics",                   "sector": "Logistics"},
    {"symbol": "GXJMFIN",     "name": "GXM Finance",                       "sector": "NBFC"},
    {"symbol": "ARMAN",       "name": "Arman Financial Services",          "sector": "NBFC"},
    {"symbol": "CREDITACC",   "name": "Credit Access Grameen",             "sector": "NBFC"},
    {"symbol": "UJJIVAN",     "name": "Ujjivan Financial Services",        "sector": "NBFC"},
    {"symbol": "SPANDANA",    "name": "Spandana Sphoorty Financial",       "sector": "NBFC"},
    {"symbol": "FUSION",      "name": "Fusion Micro Finance",              "sector": "NBFC"},
    {"symbol": "FIVESTAR",    "name": "Five-Star Business Finance",        "sector": "NBFC"},
    {"symbol": "INDOSTAR",    "name": "IndoStar Capital Finance",          "sector": "NBFC"},
    {"symbol": "INDIABULLSRE","name": "Indiabulls Real Estate",            "sector": "Real Estate"},
    {"symbol": "PURVA",       "name": "Puravankara",                       "sector": "Real Estate"},
    {"symbol": "MANYAVAR",    "name": "Vedant Fashions (Manyavar)",        "sector": "Textiles"},
    {"symbol": "CAMPUS",      "name": "Campus Activewear",                 "sector": "Consumer"},
    {"symbol": "BATAINDIA",   "name": "Bata India",                        "sector": "Consumer"},
    {"symbol": "RELAXO",      "name": "Relaxo Footwears",                  "sector": "Consumer"},
    {"symbol": "METRO",       "name": "Metro Brands",                      "sector": "Consumer"},
    {"symbol": "KESORAMIND",  "name": "Kesoram Industries",                "sector": "Cement"},
    {"symbol": "OCL",         "name": "OCL India (Odisha Cement)",         "sector": "Cement"},
    {"symbol": "STARCEMENT",  "name": "Star Cement",                       "sector": "Cement"},
    {"symbol": "SRCEM",       "name": "Shree Cement",                      "sector": "Cement"},
    {"symbol": "SPYLNA",      "name": "Spandana Sphoorty",                 "sector": "NBFC"},
    {"symbol": "HAPPIEST",    "name": "Happiest Minds Technologies",       "sector": "IT"},
    {"symbol": "AFFLE",       "name": "Affle India",                       "sector": "IT"},
    {"symbol": "ONMOBILE",    "name": "OnMobile Global",                   "sector": "IT"},
    {"symbol": "TATATECH",    "name": "Tata Technologies",                 "sector": "IT"},
    {"symbol": "MEDPLUS",     "name": "Medplus Health Services",           "sector": "Retail"},
    {"symbol": "EKMB",        "name": "EKMB",                              "sector": "Banking"},
    {"symbol": "SBFC",        "name": "SBFC Finance",                      "sector": "NBFC"},
    {"symbol": "PAISALO",     "name": "Paisalo Digital",                   "sector": "NBFC"},
    {"symbol": "SHIVALIK",    "name": "Shivalik Small Finance Bank",       "sector": "Banking"},
    {"symbol": "JANA",        "name": "Jana Small Finance Bank",           "sector": "Banking"},
    {"symbol": "SURYODAY",    "name": "Suryoday Small Finance Bank",       "sector": "Banking"},
    {"symbol": "NORTHEASTBK","name": "Northeast Small Finance Bank",      "sector": "Banking"},
    {"symbol": "FINCARE",     "name": "Fincare Small Finance Bank",        "sector": "Banking"},
    {"symbol": "LAXMIONLINE", "name": "Laxmi Organic Industries",          "sector": "Chemicals"},
    {"symbol": "LLOYDSENGG",  "name": "Lloyd Engineering Works",           "sector": "Industrial"},
    {"symbol": "GREENPANEL",  "name": "Greenpanel Industries",             "sector": "Industrial"},
    {"symbol": "CENTURYPLY",  "name": "Century Plyboards (India)",        "sector": "Industrial"},
    {"symbol": "KITEX",       "name": "Kitex Garments",                    "sector": "Textiles"},
    {"symbol": "GARWARE",     "name": "Garware Hi-Tech Films",             "sector": "Chemicals"},
    {"symbol": "GAEL",        "name": "Gujarat Ambuja Exports",            "sector": "Agrochemicals"},
    {"symbol": "RENEXT",      "name": "ReNew Energy Global",               "sector": "Utilities"},
    {"symbol": "POWERMECH",   "name": "Power Mech Projects",               "sector": "Infrastructure"},
    {"symbol": "SPGTL",       "name": "Sterling & Wilson Renewable Energy","sector": "Utilities"},
    {"symbol": "WEBSOL",      "name": "Websol Energy System",              "sector": "Utilities"},
    {"symbol": "WAAREE",      "name": "Waaree Energies",                   "sector": "Utilities"},
    {"symbol": "PREMIER",     "name": "Premier Energies",                  "sector": "Utilities"},
    {"symbol": "GESHIP",      "name": "Garden Reach Shipbuilders",         "sector": "Defence"},
    {"symbol": "SAREGAMA",    "name": "Saregama India",                    "sector": "Media"},
    {"symbol": "ANIL",        "name": "Anil Limited",                      "sector": "Chemicals"},
    {"symbol": "JUBILANT",    "name": "Jubilant Pharmova",                 "sector": "Pharma"},
    {"symbol": "JUBLINGREA",  "name": "Jubilant Ingrevia",                 "sector": "Chemicals"},
    {"symbol": "LATENTVIEW",  "name": "LatentView Analytics",             "sector": "IT"},
    {"symbol": "IDEAFORGE",   "name": "ideaForge Technology (Drones)",     "sector": "Defence"},
    {"symbol": "PARAS",       "name": "Paras Defence and Space Technologies","sector": "Defence"},
    {"symbol": "ZEN",         "name": "Zen Technologies",                  "sector": "Defence"},
    {"symbol": "CENTUM",      "name": "Centum Electronics",                "sector": "Defence"},
    {"symbol": "APOLLOMICRO","name": "Apollo Micro Systems",              "sector": "Defence"},
    {"symbol": "DRDOSYS",     "name": "DRDOSYS Technologies (DRDOSYS)",    "sector": "Defence"},
    {"symbol": "HBLPOWER",    "name": "HBL Power Systems",                 "sector": "Defence"},
    {"symbol": "ROCKETMED",   "name": "Rocket Medical (AGNI Tanker)",     "sector": "Defence"},
    {"symbol": "SASKEN",      "name": "Sasken Technologies",               "sector": "IT"},
    {"symbol": "TTML",        "name": "Tata Teleservices Maharashtra",     "sector": "Telecom"},
    {"symbol": "STLTECH",     "name": "Sterlite Technologies",             "sector": "Telecom"},
    {"symbol": "OPTIEMUS",    "name": "Optiemus Infracom",                 "sector": "Electronics"},
    {"symbol": "CYBERTECH",   "name": "Cybertech Systems and Software",    "sector": "IT"},
    {"symbol": "RAMCOIND",    "name": "Ramco Industries",                  "sector": "Industrial"},
    {"symbol": "JKPAPER",     "name": "JK Paper",                          "sector": "Paper"},
    {"symbol": "WESTCOAST",   "name": "West Coast Paper Mills",            "sector": "Paper"},
    {"symbol": "SATIA",       "name": "Satia Industries",                  "sector": "Paper"},
    {"symbol": "TAMILNADMER","name": "Tamil Nadu Mercantile Bank",        "sector": "Banking"},
    {"symbol": "AAKASH",      "name": "Aakash Educational Services",       "sector": "Education"},
    {"symbol": "CENTPUB",     "name": "Central Publisher",                 "sector": "Education"},
    {"symbol": "EDEL",        "name": "Edelweiss Financial Services",      "sector": "Financial Services"},
    {"symbol": "EDELWEISS",   "name": "Edelweiss Financial Services",      "sector": "Financial Services"},
    {"symbol": "CREDITACC",   "name": "Credit Access Grameen",             "sector": "NBFC"},
    {"symbol": "BAJAJHEAL",   "name": "Bajaj Healthtech",                  "sector": "Healthcare"},
    {"symbol": "TVSSCS",      "name": "TVS Supply Chain Solutions",        "sector": "Logistics"},
    {"symbol": "TCIEXP",      "name": "TCI Express",                       "sector": "Logistics"},
    {"symbol": "DTIL",        "name": "Dispatch Technologies (DTIL)",      "sector": "Logistics"},
    {"symbol": "SPXINDIA",    "name": "SPX Flow Technology India",         "sector": "Industrial"},
    {"symbol": "JYOTICNC",    "name": "Jyoti CNC Automation",             "sector": "Industrial"},
    {"symbol": "LATENTVIW",   "name": "LatentView Analytics",             "sector": "IT"},
    {"symbol": "RATEGAIN",    "name": "RateGain Travel Technologies",      "sector": "IT"},
    {"symbol": "MSTCLTD",     "name": "MSTC Limited",                      "sector": "Financial Services"},
    {"symbol": "IREDA",       "name": "Indian Renewable Energy Dev Agency","sector": "Finance"},
    {"symbol": "NSMILLS",     "name": "NS Mills",                          "sector": "Textiles"},
    {"symbol": "SMSPHARMA",   "name": "SMS Pharmaceuticals",               "sector": "Pharma"},
    {"symbol": "GENUSPOWER",  "name": "Genus Power Infrastructures",       "sector": "Industrial"},
    {"symbol": "INDSWFTLAB",  "name": "Ind-Swift Laboratories",            "sector": "Pharma"},
    {"symbol": "TIPSFILMS",   "name": "Tips Films",                        "sector": "Media"},
    {"symbol": "RADIOCITY",   "name": "Music Broadcast (Radio City)",      "sector": "Media"},
    {"symbol": "DBCORP",      "name": "D.B. Corp (Dainik Bhaskar)",        "sector": "Media"},
    {"symbol": "JAGSONPAL",   "name": "Jagsonpal Pharmaceuticals",         "sector": "Pharma"},
    {"symbol": "VIRINCHI",    "name": "Virinchi Limited",                  "sector": "Healthcare"},
    {"symbol": "YATARTH",     "name": "Yatharth Hospital & Trauma",        "sector": "Healthcare"},
    {"symbol": "DPWWORLD",    "name": "DP World (Hindustan Ports)",        "sector": "Logistics"},
    {"symbol": "GSPL",        "name": "Gujarat State Petronet",            "sector": "Energy"},
    {"symbol": "SABTN",       "name": "Sab Industries",                    "sector": "Industrial"},
    {"symbol": "RITES",       "name": "RITES Limited",                     "sector": "Infrastructure"},
    {"symbol": "NARMADA",     "name": "Narmada Agrobase",                  "sector": "Agrochemicals"},
    {"symbol": "SHALPAINTS",  "name": "Shalimar Paints",                   "sector": "Paints"},
    {"symbol": "KPIL",        "name": "Kalpataru Projects International",  "sector": "Infrastructure"},
    {"symbol": "SURAJEST",    "name": "Suraj Estate Developers",           "sector": "Real Estate"},
    {"symbol": "BALAJIAM",    "name": "Balaji Amines",                     "sector": "Chemicals"},
    {"symbol": "TATAINVEST",  "name": "Tata Investment Corporation",       "sector": "Diversified"},
    {"symbol": "BAJAJHIND",   "name": "Bajaj Hindusthan Sugar",            "sector": "Sugar"},
    {"symbol": "SAKTHI",      "name": "Sakthi Sugars",                     "sector": "Sugar"},
    {"symbol": "ISGEC",       "name": "ISGEC Heavy Engineering",           "sector": "Industrial"},
    {"symbol": "ELECON",      "name": "Elecon Engineering Company",        "sector": "Industrial"},
    {"symbol": "MBLINFRA",    "name": "MBL Infrastructures",               "sector": "Infrastructure"},
    {"symbol": "ASTEC",       "name": "Astec LifeSciences",                "sector": "Agrochemicals"},
    {"symbol": "VINCOIND",    "name": "Vinco Industrial Ventures",         "sector": "Industrial"},
    {"symbol": "SALZERELEC",  "name": "Salzer Electronics",                "sector": "Electricals"},
    {"symbol": "APARIND",     "name": "Apar Industries",                   "sector": "Electricals"},
    {"symbol": "CENTURYENKA","name": "Century Enka",                      "sector": "Textiles"},
    {"symbol": "TATAMETALI",  "name": "Tata Metaliks",                     "sector": "Metals"},
    {"symbol": "JAYAGROGN",   "name": "Jayagro Green",                     "sector": "Agrochemicals"},
    {"symbol": "VIMTALABS",   "name": "Vimta Labs",                        "sector": "Diagnostics"},
    {"symbol": "GENUSPAPER",  "name": "Genus Paper & Boards",              "sector": "Paper"},
    {"symbol": "GANECOS",     "name": "Ganesha Ecosphere",                 "sector": "Textiles"},
    {"symbol": "KSB",         "name": "KSB Limited",                       "sector": "Industrial"},
    {"symbol": "MAXVIL",      "name": "Max Ventures and Industries",       "sector": "Diversified"},
    {"symbol": "NUVAMA",      "name": "Nuvama Wealth Management",          "sector": "Financial Services"},
    {"symbol": "AAVAS",       "name": "Aavas Financiers",                  "sector": "NBFC"},
    {"symbol": "APTUS",       "name": "Aptus Value Housing Finance",       "sector": "NBFC"},
    {"symbol": "BAJAJHFL",    "name": "Bajaj Housing Finance",             "sector": "NBFC"},
    {"symbol": "CENTRALBK",   "name": "Central Bank of India",             "sector": "Banking"},
    {"symbol": "GANESHHOUC",  "name": "Ganesh Housing Corporation",        "sector": "Real Estate"},
    {"symbol": "SHYAMMETL",   "name": "Shyam Metalics and Energy",        "sector": "Metals"},
    {"symbol": "IMAGICAA",    "name": "Imagicaaworld Entertainment",       "sector": "Entertainment"},
    {"symbol": "EQUITAS",     "name": "Equitas Holdings",                  "sector": "Banking"},
]



def search_stocks(query: str, limit: int = 12) -> List[Dict[str, str]]:
    """
    Search ALL NSE/BSE listed stocks.
    Delegates to stock_universe which:
      - Searches 2000+ stocks from the official NSE EQUITY_L.csv
      - Falls back to yfinance Search API for any stock not in the NSE list (covers BSE)
      - Returns {symbol, name, sector, exchange} per result
    """
    if not query or len(query.strip()) < 1:
        return []
    results = stock_universe.search_universe(query.strip(), limit=limit)
    return [{"symbol": r["symbol"], "name": r["name"], "sector": r.get("sector", "NSE Listed")} for r in results]



def _is_cache_valid(symbol: str) -> bool:
    entry = _stock_cache.get(symbol)
    if not entry:
        return False
    age = (datetime.utcnow() - entry["fetched_at"]).total_seconds()
    return age < _CACHE_TTL_SECONDS


import math

def _safe_round(val: Any, digits: int = 2) -> Optional[float]:
    """Round to digits, returning None for None/NaN/Infinity."""
    try:
        if val is None:
            return None
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, digits)
    except (TypeError, ValueError):
        return None


def _sanitize_for_json(obj: Any) -> Any:
    """
    Recursively walk a dict/list/value and replace NaN, Infinity, -Infinity
    with None so FastAPI/JSON encoder never sees them.
    Called once on the full result before caching.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def _get_val(d: Any, *keys) -> Optional[float]:
    """Safely get a numeric value from a dict."""
    for k in keys:
        v = d.get(k) if isinstance(d, dict) else getattr(d, k, None)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _calculate_piotroski_score(symbol: str) -> Dict[str, Any]:
    """
    Piotroski F-Score (0-9): A 9-point accounting quality test.
    Scores each of 9 binary signals based on profitability, leverage, and efficiency.
    Score 0-2 = Weak, 3-5 = Average, 6-7 = Good, 8-9 = Very Strong.
    """
    try:
        ticker = yf.Ticker(f"{symbol}.NS", session=_session)
        info = ticker.info or {}
        
        # Get financial statements
        bs = ticker.balance_sheet        # columns = dates
        cf = ticker.cashflow
        inc = ticker.income_stmt

        if bs is None or bs.empty or inc is None or inc.empty:
            return {"score": None, "max": 9, "signals": [], "interpretation": "Data insufficient"}

        score = 0
        signals = []

        def _bs(key, col=0):
            try:
                row = bs.loc[[k for k in bs.index if key.lower() in k.lower()]]
                return float(row.iloc[0, col]) if not row.empty else None
            except Exception:
                return None

        def _inc(key, col=0):
            try:
                row = inc.loc[[k for k in inc.index if key.lower() in k.lower()]]
                return float(row.iloc[0, col]) if not row.empty else None
            except Exception:
                return None

        def _cf(key, col=0):
            try:
                row = cf.loc[[k for k in cf.index if key.lower() in k.lower()]]
                return float(row.iloc[0, col]) if not row.empty else None
            except Exception:
                return None

        total_assets_now   = _bs("Total Assets", 0) or 1
        total_assets_prev  = _bs("Total Assets", 1) or 1
        net_income         = _inc("Net Income", 0)
        net_income_prev    = _inc("Net Income", 1)
        op_cf              = _cf("Operating Cash Flow", 0)
        roa_now            = (net_income / total_assets_now) if net_income and total_assets_now else None
        roa_prev           = (net_income_prev / total_assets_prev) if net_income_prev and total_assets_prev else None

        # F1: ROA positive
        if roa_now is not None and roa_now > 0:
            score += 1
            signals.append({"name": "ROA Positive", "pass": True})
        else:
            signals.append({"name": "ROA Positive", "pass": False})

        # F2: Operating Cash Flow positive
        if op_cf is not None and op_cf > 0:
            score += 1
            signals.append({"name": "Positive Operating Cash Flow", "pass": True})
        else:
            signals.append({"name": "Positive Operating Cash Flow", "pass": False})

        # F3: ROA improving YoY
        if roa_now is not None and roa_prev is not None and roa_now > roa_prev:
            score += 1
            signals.append({"name": "ROA Improving YoY", "pass": True})
        else:
            signals.append({"name": "ROA Improving YoY", "pass": False})

        # F4: Accruals (OCF/Assets > ROA — earnings quality)
        accrual = (op_cf / total_assets_now) if op_cf else None
        if accrual is not None and roa_now is not None and accrual > roa_now:
            score += 1
            signals.append({"name": "High Earnings Quality (OCF > ROA)", "pass": True})
        else:
            signals.append({"name": "High Earnings Quality (OCF > ROA)", "pass": False})

        # F5: Leverage decreasing
        lt_debt_now  = _bs("Long Term Debt", 0) or 0
        lt_debt_prev = _bs("Long Term Debt", 1) or 0
        lev_now  = lt_debt_now / total_assets_now
        lev_prev = lt_debt_prev / total_assets_prev
        if lev_now < lev_prev:
            score += 1
            signals.append({"name": "Leverage Decreasing", "pass": True})
        else:
            signals.append({"name": "Leverage Decreasing", "pass": False})

        # F6: Current ratio improving
        cr_now  = _get_val(info, "currentRatio")
        cr_prev_assets  = _bs("Current Assets", 1) or 0
        cr_prev_liab    = _bs("Current Liabilities", 1) or 1
        cr_prev = cr_prev_assets / cr_prev_liab if cr_prev_liab else None
        if cr_now is not None and cr_prev is not None and cr_now > cr_prev:
            score += 1
            signals.append({"name": "Current Ratio Improving", "pass": True})
        else:
            signals.append({"name": "Current Ratio Improving", "pass": False})

        # F7: No dilution (shares not increased)
        shares_now  = _get_val(info, "sharesOutstanding")
        shares_prev_row = bs.loc[[k for k in bs.index if "ordinary" in k.lower() or "share" in k.lower() and "capital" in k.lower()]]
        shares_prev = float(shares_prev_row.iloc[0, 1]) if not shares_prev_row.empty else None
        if shares_now is not None and shares_prev is not None and shares_now <= shares_prev * 1.02:  # 2% tolerance
            score += 1
            signals.append({"name": "No Share Dilution", "pass": True})
        else:
            signals.append({"name": "No Share Dilution", "pass": False})

        # F8: Gross margin improving
        rev_now  = _inc("Total Revenue", 0) or 1
        rev_prev = _inc("Total Revenue", 1) or 1
        cogs_now  = _inc("Cost Of Revenue", 0) or _inc("Cost of Goods Sold", 0) or 0
        cogs_prev = _inc("Cost Of Revenue", 1) or _inc("Cost of Goods Sold", 1) or 0
        gm_now  = (rev_now - cogs_now) / rev_now if rev_now else None
        gm_prev = (rev_prev - cogs_prev) / rev_prev if rev_prev else None
        if gm_now is not None and gm_prev is not None and gm_now > gm_prev:
            score += 1
            signals.append({"name": "Gross Margin Improving", "pass": True})
        else:
            signals.append({"name": "Gross Margin Improving", "pass": False})

        # F9: Asset turnover improving
        at_now  = rev_now / total_assets_now
        at_prev = rev_prev / total_assets_prev
        if at_now > at_prev:
            score += 1
            signals.append({"name": "Asset Turnover Improving", "pass": True})
        else:
            signals.append({"name": "Asset Turnover Improving", "pass": False})

        if score >= 8:
            interpretation = "Very Strong — 8-9 quality signals passing"
        elif score >= 6:
            interpretation = "Good — financially sound company"
        elif score >= 3:
            interpretation = "Average — some quality concerns"
        else:
            interpretation = "Weak — multiple quality red flags"

        return {"score": score, "max": 9, "signals": signals, "interpretation": interpretation}

    except Exception as e:
        logger.warning(f"Piotroski score failed for {symbol}: {e}")
        return {"score": None, "max": 9, "signals": [], "interpretation": "Data insufficient"}


def _calculate_altman_z_score(symbol: str, info: Dict) -> Dict[str, Any]:
    """
    Altman Z-Score (modified for non-manufacturing / emerging markets).
    Z = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
    X1 = Working Capital / Total Assets
    X2 = Retained Earnings / Total Assets
    X3 = EBIT / Total Assets
    X4 = Book Value of Equity / Total Liabilities
    """
    try:
        ticker = yf.Ticker(f"{symbol}.NS", session=_session)
        bs = ticker.balance_sheet
        inc = ticker.income_stmt

        if bs is None or bs.empty:
            return {"z_score": None, "zone": "Data insufficient", "zone_color": "#888"}

        def _g(df, key, col=0):
            try:
                row = df.loc[[k for k in df.index if key.lower() in k.lower()]]
                return float(row.iloc[0, col]) if not row.empty else None
            except Exception:
                return None

        total_assets = _g(bs, "Total Assets") or 1
        current_assets = _g(bs, "Current Assets") or 0
        current_liab   = _g(bs, "Current Liabilities") or 0
        retained_earn  = _g(bs, "Retained Earnings") or 0
        total_equity   = _g(bs, "Stockholders Equity") or _g(bs, "Total Equity") or 0
        total_liab     = _g(bs, "Total Liabilities") or 1
        ebit           = None
        if inc is not None and not inc.empty:
            ebit = _g(inc, "EBIT") or _g(inc, "Operating Income")

        working_capital = current_assets - current_liab

        X1 = working_capital / total_assets
        X2 = retained_earn / total_assets
        X3 = (ebit / total_assets) if ebit else 0
        X4 = total_equity / total_liab if total_liab else 0

        z = 6.56 * X1 + 3.26 * X2 + 6.72 * X3 + 1.05 * X4
        z = round(z, 2)

        if z > 2.6:
            zone = "Safe Zone"
            zone_color = "#00C48C"
            zone_desc = "Low financial distress risk"
        elif z > 1.1:
            zone = "Grey Zone"
            zone_color = "#f59e0b"
            zone_desc = "Moderate risk — monitor closely"
        else:
            zone = "Distress Zone"
            zone_color = "#ef4444"
            zone_desc = "High financial distress risk"

        return {"z_score": z, "zone": zone, "zone_color": zone_color, "zone_desc": zone_desc}

    except Exception as e:
        logger.warning(f"Altman Z-Score failed for {symbol}: {e}")
        return {"z_score": None, "zone": "Data insufficient", "zone_color": "#888", "zone_desc": ""}


def _calculate_graham_number(fundamentals: Dict) -> Optional[Dict[str, Any]]:
    """
    Graham Number = sqrt(22.5 * EPS * Book Value Per Share)
    Compares this intrinsic value to current market price.
    """
    try:
        eps = fundamentals.get("trailing_eps") or fundamentals.get("eps")
        bvps = fundamentals.get("book_value")
        if eps is None or bvps is None:
            return None
        eps_f = float(eps)
        bvps_f = float(bvps)
        if eps_f <= 0 or bvps_f <= 0:
            return None
        graham_num = (22.5 * eps_f * bvps_f) ** 0.5
        return {"graham_number": round(graham_num, 2), "eps_used": round(eps_f, 2), "bvps_used": round(bvps_f, 2)}
    except Exception:
        return None


def _fetch_earnings_surprise(symbol: str) -> List[Dict[str, Any]]:
    """
    Fetch last 4 quarters earnings vs. estimates (surprise %).
    Returns list of {quarter, actual, estimate, surprise_pct, beat}.
    """
    try:
        ticker = yf.Ticker(f"{symbol}.NS", session=_session)
        hist = ticker.earnings_history
        if hist is None or (hasattr(hist, 'empty') and hist.empty):
            return []
        results = []
        if hasattr(hist, 'iterrows'):
            for _, row in list(hist.iterrows())[-4:]:
                actual   = row.get("epsActual") or row.get("Reported EPS")
                estimate = row.get("epsEstimate") or row.get("EPS Estimate")
                period   = str(row.get("period") or row.get("Date") or row.name or "")
                if actual is not None and estimate is not None:
                    try:
                        a, e = float(actual), float(estimate)
                        surprise = round(((a - e) / abs(e)) * 100, 1) if e != 0 else 0
                        results.append({
                            "quarter": period[:10],
                            "actual": round(a, 2),
                            "estimate": round(e, 2),
                            "surprise_pct": surprise,
                            "beat": surprise > 0,
                        })
                    except Exception:
                        continue
        return results[-4:]
    except Exception as e:
        logger.debug(f"Earnings surprise fetch failed for {symbol}: {e}")
        return []


def get_live_price(symbol: str) -> Dict[str, Any]:
    """
    Lightweight real-time price fetch via yfinance fast_info.
    Bypasses the 4-hour full detail cache.
    Used for the /stock/{symbol}/live endpoint.
    """
    symbol = symbol.upper().replace(".NS", "").strip()
    try:
        ticker = yf.Ticker(f"{symbol}.NS", session=_session)
        fi = ticker.fast_info
        price    = _safe_round(getattr(fi, "last_price", None))
        prev     = _safe_round(getattr(fi, "previous_close", None))
        high     = _safe_round(getattr(fi, "day_high", None))
        low      = _safe_round(getattr(fi, "day_low", None))
        volume   = getattr(fi, "last_volume", None)
        change     = _safe_round(price - prev) if price and prev else None
        change_pct = _safe_round(((price - prev) / prev) * 100) if price and prev and prev != 0 else None
        return {
            "symbol": symbol,
            "current_price": price,
            "prev_close": prev,
            "change": change,
            "change_pct": change_pct,
            "day_high": high,
            "day_low": low,
            "volume": int(volume) if volume else None,
            "fetched_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.warning(f"Live price fetch failed for {symbol}: {e}")
        return {"symbol": symbol, "current_price": None, "error": str(e)}



def get_stock_detail(symbol: str) -> Dict[str, Any]:
    """
    Main entry point: returns full stock detail dict.
    Cached for 4 hours per symbol.
    """
    symbol = symbol.upper().replace(".NS", "").strip()

    if _is_cache_valid(symbol):
        logger.debug(f"Stock cache hit: {symbol}")
        cached = _stock_cache[symbol]["data"]
        # Always inject fresh live price even from cache (critical for swing traders)
        try:
            fresh = get_live_price(symbol)
            if fresh.get("current_price"):
                cached = dict(cached)  # shallow copy to avoid mutating cache
                cached["current_price"] = fresh["current_price"]
                cached["change"]        = fresh["change"]
                cached["change_pct"]    = fresh["change_pct"]
                cached["day_high"]      = fresh["day_high"]
                cached["day_low"]       = fresh["day_low"]
                cached["volume"]        = fresh["volume"]
                cached["prev_close"]    = fresh["prev_close"]
                cached["price_refreshed_at"] = fresh["fetched_at"]
                logger.debug(f"Live price injected into cache for {symbol}: {fresh['current_price']}")
        except Exception as e:
            logger.debug(f"Live price refresh failed for cached {symbol}: {e}")
        return cached


    logger.info(f"Fetching stock detail for: {symbol}")
    data: Dict[str, Any] = {"symbol": symbol, "fetched_at": datetime.utcnow().isoformat()}

    # 1. Live price data via yfinance
    price_data = _fetch_price_data(symbol)
    data.update(price_data)

    # 2. Fundamentals via yfinance (fundamentals_fetcher)
    raw_fundamentals: Dict = {}
    try:
        raw_fundamentals = fetch_fundamentals(symbol)
        data["fundamentals"] = {
            # Valuation
            "pe_ratio":           _safe_round(raw_fundamentals.get("pe_ratio")),
            "forward_pe":         _safe_round(raw_fundamentals.get("forward_pe")),
            "pb_ratio":           _safe_round(raw_fundamentals.get("pb_ratio")),
            "ps_ratio":           _safe_round(raw_fundamentals.get("ps_ratio")),
            "peg_ratio":          _safe_round(raw_fundamentals.get("peg_ratio")),
            "ev_ebitda":          _safe_round(raw_fundamentals.get("ev_ebitda")),
            # Profitability
            "roe":                _safe_round(raw_fundamentals.get("roe")),
            "roa":                _safe_round(raw_fundamentals.get("roa")),
            "roce":               _safe_round(raw_fundamentals.get("roce")),
            "profit_margin":      _safe_round(raw_fundamentals.get("profit_margin")),
            "operating_margin":   _safe_round(raw_fundamentals.get("operating_margin")),
            "gross_margin":       _safe_round(raw_fundamentals.get("gross_margin")),
            # Safety
            "debt_to_equity":     _safe_round(raw_fundamentals.get("debt_to_equity")),
            "current_ratio":      _safe_round(raw_fundamentals.get("current_ratio")),
            "quick_ratio":        _safe_round(raw_fundamentals.get("quick_ratio")),
            # Size / income
            "market_cap":         _safe_round(raw_fundamentals.get("market_cap")),
            "enterprise_value":   _safe_round(raw_fundamentals.get("enterprise_value")),
            "book_value":         _safe_round(raw_fundamentals.get("book_value")),
            "revenue_ttm":        _safe_round(raw_fundamentals.get("revenue_ttm")),
            "ebitda_ttm":         _safe_round(raw_fundamentals.get("ebitda_ttm")),
            "free_cash_flow":     _safe_round(raw_fundamentals.get("free_cash_flow")),
            # Dividends
            "dividend_yield":     _safe_round(raw_fundamentals.get("dividend_yield")),
            "dividend_rate":      _safe_round(raw_fundamentals.get("dividend_rate")),
            "payout_ratio":       _safe_round(raw_fundamentals.get("payout_ratio")),
            # Growth
            "revenue_growth_1yr": _safe_round(raw_fundamentals.get("revenue_growth_1yr")),
            "profit_growth_1yr":  _safe_round(raw_fundamentals.get("profit_growth_1yr")),
            "revenue_growth_3yr": _safe_round(raw_fundamentals.get("revenue_growth_3yr")),
            "profit_growth_3yr":  _safe_round(raw_fundamentals.get("profit_growth_3yr")),
            # Identity
            "company_name":       raw_fundamentals.get("company_name"),
            "sector":             raw_fundamentals.get("sector"),
            "industry":           raw_fundamentals.get("industry"),
            # Source metadata
            "source":             raw_fundamentals.get("source", "yfinance"),
        }
        # Shareholding — now from yfinance heldPercentInsiders / institutions
        data["shareholding"] = {
            "promoter": _safe_round(raw_fundamentals.get("promoter_holding")),
            "fii":      _safe_round(raw_fundamentals.get("fii_holding")),
            "dii":      _safe_round(raw_fundamentals.get("dii_holding")),
        }
        # Compute Public % (residual)
        held = sum(
            v for v in [
                data["shareholding"]["promoter"],
                data["shareholding"]["fii"],
                data["shareholding"]["dii"],
            ] if v is not None
        )
        data["shareholding"]["public"] = _safe_round(max(0, 100 - held)) if held > 0 else None

        # Override company name from fundamentals if price fetch got symbol only
        if data.get("company_name") == symbol and raw_fundamentals.get("company_name"):
            data["company_name"] = raw_fundamentals["company_name"]

    except Exception as e:
        logger.error(f"Fundamentals fetch failed for {symbol}: {e}")
        data["fundamentals"] = {}
        data["shareholding"] = {}


    # 3. FII Activity (trend analysis from shareholding)
    data["fii_activity"] = _compute_fii_activity(data.get("shareholding", {}))

    # 4. Top Institutional Holders from yfinance
    data["institutional_holders"] = _fetch_institutional_holders(symbol)

    # 5. Company-specific recent news
    data["recent_news"] = _fetch_company_news(symbol, data.get("company_name") or symbol)

    # 6. Analyst Verdict
    data["analyst_verdict"] = _generate_analyst_verdict(
        symbol=symbol,
        fundamentals=data.get("fundamentals", {}),
        shareholding=data.get("shareholding", {}),
        price_data=price_data,
    )

    # 7. ─── EXCLUSIVE DIFFERENTIATING DATA ────────────────────────────────────
    # Graham Number (intrinsic value estimate)
    graham = _calculate_graham_number({
        **raw_fundamentals,
        "trailing_eps": price_data.get("eps"),
    })
    data["graham_number"] = graham
    if graham and price_data.get("current_price"):
        cp = price_data["current_price"]
        gn = graham["graham_number"]
        data["graham_number"]["current_price"] = cp
        data["graham_number"]["premium_pct"] = _safe_round(((cp - gn) / gn) * 100) if gn else None
        data["graham_number"]["is_undervalued"] = cp < gn

    # Piotroski F-Score (run in try block — requires financial statements)
    data["piotroski"] = _calculate_piotroski_score(symbol)

    # Altman Z-Score
    data["altman_z"] = _calculate_altman_z_score(symbol, {})

    # Earnings Surprise History (last 4 quarters)
    data["earnings_surprise"] = _fetch_earnings_surprise(symbol)


    # Sanitize all float values (NaN / Infinity crash the JSON encoder)
    data = _sanitize_for_json(data)

    # Cache result
    _stock_cache[symbol] = {"data": data, "fetched_at": datetime.utcnow()}
    logger.info(f"Stock detail cached for {symbol}")
    return data


def _fetch_price_data(symbol: str) -> Dict[str, Any]:
    """Fetch live price data via yfinance fast_info + info (fallback: download)."""
    ns_symbol = f"{symbol}.NS"

    # NOTE: External IP API (65.0.104.9) was removed — it timed out on every call.
    # yfinance fast_info is reliable, lightweight, and doesn't risk 429 rate limits.


    # ── Attempt 1: fast_info (lightweight, no 429 risk) ─────────────────────────

    for attempt in range(3):
        try:
            ticker = yf.Ticker(ns_symbol, session=_session)
            fi = ticker.fast_info

            current_price = getattr(fi, "last_price", None) or getattr(fi, "regularMarketPrice", None)
            prev_close    = getattr(fi, "previous_close", None) or getattr(fi, "regularMarketPreviousClose", None)
            day_high      = getattr(fi, "day_high", None)
            day_low       = getattr(fi, "day_low", None)
            volume        = getattr(fi, "last_volume", None) or getattr(fi, "regularMarketVolume", None)
            week_52_high  = getattr(fi, "year_high", None) or getattr(fi, "fiftyTwoWeekHigh", None)
            week_52_low   = getattr(fi, "year_low", None) or getattr(fi, "fiftyTwoWeekLow", None)
            market_cap    = getattr(fi, "market_cap", None)
            avg_volume    = getattr(fi, "three_month_average_volume", None)
            exchange      = getattr(fi, "exchange", "NSE")
            currency      = getattr(fi, "currency", "INR")

            change, change_pct = None, None
            if current_price and prev_close and prev_close != 0:
                change     = _safe_round(current_price - prev_close)
                change_pct = _safe_round(((current_price - prev_close) / prev_close) * 100)

            # Try to get longName via info (lightweight cache hit if already fetched)
            company_name = symbol
            try:
                info = ticker.info or {}
                company_name = info.get("longName") or info.get("shortName") or symbol
                eps          = _safe_round(info.get("trailingEps"))
                beta         = _safe_round(info.get("beta"))
                sector_yf    = info.get("sector", "")
                industry_yf  = info.get("industry", "")
                description  = (info.get("longBusinessSummary") or "")[:500]
            except Exception:
                eps = beta = None
                sector_yf = industry_yf = description = ""

            if current_price is not None:
                logger.info(f"fast_info succeeded for {symbol}: price={current_price}")
                return {
                    "company_name":  company_name,
                    "exchange":      exchange,
                    "currency":      currency,
                    "current_price": _safe_round(current_price),
                    "prev_close":    _safe_round(prev_close),
                    "change":        change,
                    "change_pct":    change_pct,
                    "day_high":      _safe_round(day_high),
                    "day_low":       _safe_round(day_low),
                    "week_52_high":  _safe_round(week_52_high),
                    "week_52_low":   _safe_round(week_52_low),
                    "volume":        int(volume) if volume else None,
                    "avg_volume":    int(avg_volume) if avg_volume else None,
                    "market_cap_yf": int(market_cap) if market_cap else None,
                    "eps":           eps,
                    "beta":          beta,
                    "sector_yf":     sector_yf,
                    "industry_yf":   industry_yf,
                    "description":   description,
                }
        except Exception as e:
            logger.warning(f"fast_info attempt {attempt+1} failed for {symbol}: {e}")
            if attempt < 2:
                time.sleep(2 + attempt * 2)

    # ── Attempt 2: yfinance download() for OHLCV ──────────────────────────────
    try:
        logger.info(f"Falling back to download() for {symbol}")
        df = yf.download(
            ns_symbol,
            period="2d",
            interval="1d",
            progress=False,
            session=_session,
            auto_adjust=True,
        )
        if df is not None and not df.empty:
            row = df.iloc[-1]
            prev_row = df.iloc[-2] if len(df) > 1 else None

            current_price = float(row.get("Close", 0) or 0) or None
            prev_close    = float(prev_row["Close"]) if prev_row is not None else None
            day_high      = float(row.get("High", 0) or 0) or None
            day_low       = float(row.get("Low", 0) or 0) or None
            volume        = int(row.get("Volume", 0) or 0) or None

            change, change_pct = None, None
            if current_price and prev_close and prev_close != 0:
                change     = _safe_round(current_price - prev_close)
                change_pct = _safe_round(((current_price - prev_close) / prev_close) * 100)

            logger.info(f"download() succeeded for {symbol}: price={current_price}")
            return {
                "company_name":  symbol,
                "exchange":      "NSE",
                "currency":      "INR",
                "current_price": _safe_round(current_price),
                "prev_close":    _safe_round(prev_close),
                "change":        change,
                "change_pct":    change_pct,
                "day_high":      _safe_round(day_high),
                "day_low":       _safe_round(day_low),
                "week_52_high":  None,
                "week_52_low":   None,
                "volume":        volume,
                "avg_volume":    None,
                "market_cap_yf": None,
                "eps":           None,
                "beta":          None,
                "sector_yf":     "",
                "industry_yf":   "",
                "description":   "",
            }
    except Exception as e:
        logger.error(f"download() fallback also failed for {symbol}: {e}")

    # ── Attempt 3: Try BSE (.BO) ticker ───────────────────────────────────────
    bo_symbol = f"{symbol}.BO"
    try:
        logger.info(f"Trying BSE fallback for {symbol} via {bo_symbol}")
        ticker = yf.Ticker(bo_symbol, session=_session)
        fi = ticker.fast_info
        current_price = getattr(fi, "last_price", None) or getattr(fi, "regularMarketPrice", None)
        if current_price and current_price > 0:
            prev_close = getattr(fi, "previous_close", None)
            day_high   = getattr(fi, "day_high", None)
            day_low    = getattr(fi, "day_low", None)
            volume     = getattr(fi, "last_volume", None)
            week_52_high = getattr(fi, "year_high", None)
            week_52_low  = getattr(fi, "year_low", None)
            market_cap   = getattr(fi, "market_cap", None)
            change, change_pct = None, None
            if prev_close and prev_close != 0:
                change     = _safe_round(current_price - prev_close)
                change_pct = _safe_round(((current_price - prev_close) / prev_close) * 100)
            try:
                info = ticker.info or {}
                company_name = info.get("longName") or info.get("shortName") or symbol
                eps = _safe_round(info.get("trailingEps"))
                beta = _safe_round(info.get("beta"))
                sector_yf = info.get("sector", "")
                industry_yf = info.get("industry", "")
                description = (info.get("longBusinessSummary") or "")[:500]
            except Exception:
                company_name = symbol
                eps = beta = None
                sector_yf = industry_yf = description = ""
            logger.info(f"BSE (.BO) fallback succeeded for {symbol}: price={current_price}")
            return {
                "company_name":  company_name,
                "exchange":      "BSE",
                "currency":      "INR",
                "current_price": _safe_round(current_price),
                "prev_close":    _safe_round(prev_close),
                "change":        change,
                "change_pct":    change_pct,
                "day_high":      _safe_round(day_high),
                "day_low":       _safe_round(day_low),
                "week_52_high":  _safe_round(week_52_high),
                "week_52_low":   _safe_round(week_52_low),
                "volume":        int(volume) if volume else None,
                "avg_volume":    None,
                "market_cap_yf": int(market_cap) if market_cap else None,
                "eps":           eps,
                "beta":          beta,
                "sector_yf":     sector_yf,
                "industry_yf":   industry_yf,
                "description":   description,
            }
    except Exception as e:
        logger.error(f"BSE fallback also failed for {symbol}: {e}")

    # ── All attempts exhausted ─────────────────────────────────────────────────
    logger.error(f"All price fetch methods failed for {symbol}")
    return {
        "company_name":  symbol,
        "exchange":      "NSE",
        "currency":      "INR",
        "current_price": None,
        "prev_close":    None,
        "change":        None,
        "change_pct":    None,
        "day_high":      None,
        "day_low":       None,
        "week_52_high":  None,
        "week_52_low":   None,
        "volume":        None,
        "avg_volume":    None,
        "market_cap_yf": None,
        "eps":           None,
        "beta":          None,
        "sector_yf":     "",
        "industry_yf":   "",
        "description":   "",
    }


def _fetch_institutional_holders(symbol: str) -> List[Dict[str, Any]]:
    """Fetch top institutional holders from yfinance."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS", session=_session)
        holders = ticker.institutional_holders
        if holders is None or holders.empty:
            return []
        results = []
        for _, row in holders.head(6).iterrows():
            name = str(row.get("Holder", "") or "")
            shares = row.get("Shares") or row.get("shares")
            pct = row.get("% Out") or row.get("pctHeld")
            value = row.get("Value") or row.get("value")
            try:
                shares_int = int(shares) if shares is not None else None
            except Exception:
                shares_int = None
            try:
                pct_float = _safe_round(float(pct) * 100 if pct and float(pct) < 1 else float(pct) if pct else None)
            except Exception:
                pct_float = None
            try:
                value_cr = _safe_round(float(value) / 1e7) if value else None  # convert to Crore
            except Exception:
                value_cr = None
            if name:
                results.append({
                    "holder": name,
                    "shares": shares_int,
                    "pct_held": pct_float,
                    "value_cr": value_cr,
                })
        return results
    except Exception as e:
        logger.warning(f"Institutional holders fetch failed for {symbol}: {e}")
        return []


def _compute_fii_activity(shareholding: Dict) -> Dict[str, Any]:
    """
    Since we only have current FII %, we provide a qualitative signal
    based on the FII holding level and compare it to typical thresholds.
    """
    fii = shareholding.get("fii")
    if fii is None:
        return {"trend": "UNKNOWN", "note": "Data not available", "fii_pct": None}

    if fii >= 30:
        trend = "HEAVILY_HELD"
        note = f"FIIs hold {fii}% — very high institutional confidence"
        color = "green"
    elif fii >= 20:
        trend = "WELL_HELD"
        note = f"FIIs hold {fii}% — strong institutional interest"
        color = "green"
    elif fii >= 10:
        trend = "MODERATE"
        note = f"FIIs hold {fii}% — moderate institutional presence"
        color = "yellow"
    elif fii >= 5:
        trend = "LOW"
        note = f"FIIs hold {fii}% — limited foreign institutional interest"
        color = "orange"
    else:
        trend = "MINIMAL"
        note = f"FIIs hold {fii}% — very low FII interest"
        color = "red"

    return {
        "trend": trend,
        "note": note,
        "fii_pct": fii,
        "color": color,
    }


def _fetch_company_news(symbol: str, company_name: str) -> List[Dict[str, Any]]:
    """
    Fetch recent news filtered to this company from yfinance news feed.
    Falls back to empty list gracefully.
    """
    news_items = []
    try:
        ticker = yf.Ticker(f"{symbol}.NS", session=_session)
        raw_news = getattr(ticker, 'news', None) or []
        seen_titles = set()

        def _parse_item(item: dict) -> dict | None:
            """Parse both old and new yfinance news formats."""
            # New format (yfinance >= 0.2.37): nested under 'content'
            content = item.get("content") or {}
            title = (
                content.get("title")
                or item.get("title")
                or ""
            ).strip()
            if not title or title in seen_titles:
                return None
            seen_titles.add(title)

            # URL
            url = (
                (content.get("clickThroughUrl") or {}).get("url")
                or (content.get("canonicalUrl") or {}).get("url")
                or item.get("link")
                or ""
            )

            # Publisher
            provider = content.get("provider") or {}
            source = (
                provider.get("displayName")
                or item.get("publisher")
                or (item.get("source") or {}).get("name", "")
                or ""
            )

            # Timestamp
            pub_ts = (
                content.get("pubDate")
                or item.get("providerPublishTime")
                or item.get("publishTime")
            )
            pub_str = ""
            if pub_ts:
                try:
                    if isinstance(pub_ts, (int, float)):
                        pub_str = datetime.utcfromtimestamp(pub_ts).strftime("%d %b %Y, %I:%M %p")
                    else:
                        # ISO string from new format
                        from dateutil import parser as dtparser
                        pub_str = dtparser.parse(pub_ts).strftime("%d %b %Y, %I:%M %p")
                except Exception:
                    pub_str = str(pub_ts)[:16]

            # Thumbnail
            thumbnail = ""
            thumb_list = (item.get("thumbnail") or {}).get("resolutions") or []
            if thumb_list:
                thumbnail = thumb_list[0].get("url", "")
            if not thumbnail:
                thumbnail = (content.get("thumbnail") or {}).get("url", "")

            return {
                "title":        title,
                "source":       source,
                "url":          url,
                "published_at": pub_str,
                "thumbnail":    thumbnail,
            }

        for item in raw_news[:12]:
            parsed = _parse_item(item)
            if parsed:
                news_items.append(parsed)

        if len(news_items) < 3:
            # Fallback: try non-NS ticker
            ticker2 = yf.Ticker(symbol)
            raw2 = getattr(ticker2, 'news', None) or []
            for item in raw2[:6]:
                parsed = _parse_item(item)
                if parsed:
                    news_items.append(parsed)

    except Exception as e:
        logger.warning(f"News fetch failed for {symbol}: {e}")

    return news_items[:8]


def _generate_analyst_verdict(
    symbol: str,
    fundamentals: Dict,
    shareholding: Dict,
    price_data: Dict,
) -> Dict[str, Any]:
    """
    Enhanced rule-based analyst verdict engine.
    Scores across 8 dimensions using the full yfinance fundamentals:
    Valuation | Profitability | Margin Quality | Debt Safety |
    Growth | Dividend | FII/Promoter | Price Momentum
    """
    score = 0
    max_score = 0
    insights = []
    risks = []

    pe           = fundamentals.get("pe_ratio")
    forward_pe   = fundamentals.get("forward_pe")
    pb           = fundamentals.get("pb_ratio")
    roe          = fundamentals.get("roe")
    roa          = fundamentals.get("roa")
    roce         = fundamentals.get("roce")
    de           = fundamentals.get("debt_to_equity")
    current_r    = fundamentals.get("current_ratio")
    rev_growth   = fundamentals.get("revenue_growth_3yr") or fundamentals.get("revenue_growth_1yr")
    profit_growth= fundamentals.get("profit_growth_3yr") or fundamentals.get("profit_growth_1yr")
    div_yield    = fundamentals.get("dividend_yield")
    pm           = fundamentals.get("profit_margin")
    op_margin    = fundamentals.get("operating_margin")
    fii_pct      = shareholding.get("fii")
    promoter_pct = shareholding.get("promoter")
    change_pct   = price_data.get("change_pct")
    week_52_high = price_data.get("week_52_high")
    current_price= price_data.get("current_price")

    # ── 1. Valuation — PE (25 pts) ────────────────────────────────────────────
    if pe is not None and pe > 0:
        max_score += 25
        if pe <= 12:
            score += 25
            insights.append(f"Attractively valued at PE {pe:.1f}x — significantly below market average")
        elif pe <= 18:
            score += 22
            insights.append(f"Good valuation at PE {pe:.1f}x — below Nifty 50 average")
        elif pe <= 25:
            score += 16
            insights.append(f"Fair valuation at PE {pe:.1f}x — reasonably priced")
        elif pe <= 40:
            score += 9
            insights.append(f"PE at {pe:.1f}x — premium valuation, growth must justify it")
        else:
            score += 3
            risks.append(f"High PE of {pe:.1f}x — significant growth expectations already priced in")

    # Forward PE confirmation bonus
    if forward_pe is not None and pe is not None and forward_pe > 0 and pe > 0:
        if forward_pe < pe * 0.85:
            insights.append(f"Forward PE ({forward_pe:.1f}x) well below trailing — earnings expected to grow")

    # PB sanity check
    if pb is not None and pb > 0:
        if pb <= 1.5 and pe is not None and pe > 0:
            insights.append(f"Low PB of {pb:.1f}x — trading near or below book value")
        elif pb > 15:
            risks.append(f"Very high PB of {pb:.1f}x — priced for exceptional growth")

    # ── 2. Profitability — ROE (20 pts) ───────────────────────────────────────
    if roe is not None:
        max_score += 20
        if roe >= 25:
            score += 20
            insights.append(f"Excellent ROE of {roe:.1f}% — top-tier shareholder value creation")
        elif roe >= 18:
            score += 16
            insights.append(f"Strong ROE of {roe:.1f}% — well above market average")
        elif roe >= 12:
            score += 11
            insights.append(f"Good ROE of {roe:.1f}% — above average profitability")
        elif roe >= 8:
            score += 6
        else:
            score += 2
            risks.append(f"Low ROE of {roe:.1f}% — capital efficiency needs improvement")

    # ROA supplement
    if roa is not None:
        if roa >= 12:
            insights.append(f"High ROA of {roa:.1f}% — efficient asset utilisation")
        elif roa is not None and roa < 3:
            risks.append(f"Low ROA of {roa:.1f}% — assets not generating adequate returns")

    # ── 3. Margin Quality (15 pts) ────────────────────────────────────────────
    if pm is not None or op_margin is not None:
        max_score += 15
        margin = pm or op_margin or 0
        if margin >= 25:
            score += 15
            insights.append(f"Premium profit margin of {margin:.1f}% — high-quality business model")
        elif margin >= 15:
            score += 12
            insights.append(f"Healthy net margin of {margin:.1f}% — efficient cost structure")
        elif margin >= 8:
            score += 8
        elif margin >= 3:
            score += 4
        else:
            score += 1
            risks.append(f"Thin margin of {margin:.1f}% — vulnerable to cost or revenue shocks")

    # ── 4. Debt Safety (15 pts) ───────────────────────────────────────────────
    if de is not None:
        max_score += 15
        if de <= 0.1:
            score += 15
            insights.append("Virtually debt-free — extremely low financial risk")
        elif de <= 0.5:
            score += 13
            insights.append(f"Low D/E of {de:.2f}x — strong balance sheet")
        elif de <= 1.0:
            score += 9
            insights.append(f"Conservative D/E of {de:.2f}x — manageable leverage")
        elif de <= 2.0:
            score += 5
        else:
            score += 0
            risks.append(f"High debt at D/E {de:.2f}x — monitor interest coverage and cash flows")

    # Current ratio bonus
    if current_r is not None:
        if current_r >= 2.0:
            insights.append(f"Strong current ratio ({current_r:.1f}x) — ample short-term liquidity")
        elif current_r < 1.0:
            risks.append(f"Current ratio of {current_r:.1f}x — potential short-term liquidity stress")

    # ── 5. Growth Quality (20 pts) ────────────────────────────────────────────
    if rev_growth is not None or profit_growth is not None:
        max_score += 20
        values = [v for v in [rev_growth, profit_growth] if v is not None]
        avg_growth = sum(values) / len(values) if values else 0

        if avg_growth >= 25:
            score += 20
            insights.append(f"Exceptional growth — revenue/profit compounding at >{int(avg_growth)}% CAGR")
        elif avg_growth >= 18:
            score += 17
            insights.append(f"Strong growth momentum — compounding at ~{int(avg_growth)}% CAGR")
        elif avg_growth >= 10:
            score += 12
            insights.append(f"Steady growth — ~{int(avg_growth)}% CAGR is above inflation + economy")
        elif avg_growth >= 5:
            score += 7
        elif avg_growth >= 0:
            score += 3
        else:
            score += 0
            risks.append(f"Declining revenues/profits — negative {abs(int(avg_growth))}% growth trend")

    # ── 6. Dividend (5 pts) ───────────────────────────────────────────────────
    if div_yield is not None:
        max_score += 5
        if div_yield >= 3:
            score += 5
            insights.append(f"Attractive dividend yield of {div_yield:.1f}% — income + growth combination")
        elif div_yield >= 1.5:
            score += 3
        elif div_yield > 0:
            score += 1

    # ── 7. Institutional Confidence — FII (10 pts) ────────────────────────────
    if fii_pct is not None:
        max_score += 10
        if fii_pct >= 25:
            score += 10
            insights.append(f"High FII ownership ({fii_pct:.1f}%) — strong global fund confidence")
        elif fii_pct >= 15:
            score += 7
            insights.append(f"Solid FII ownership ({fii_pct:.1f}%) — institutional-grade stock")
        elif fii_pct >= 8:
            score += 4
        elif fii_pct >= 3:
            score += 2

    # ── 8. Promoter Holding (10 pts) ──────────────────────────────────────────
    if promoter_pct is not None:
        max_score += 10
        if promoter_pct >= 60:
            score += 10
            insights.append(f"Very high promoter stake ({promoter_pct:.1f}%) — founders deeply committed")
        elif promoter_pct >= 50:
            score += 8
            insights.append(f"Strong promoter holding ({promoter_pct:.1f}%) — high skin-in-the-game")
        elif promoter_pct >= 35:
            score += 5
        elif promoter_pct < 20:
            risks.append(f"Low promoter stake ({promoter_pct:.1f}%) — governance or dilution risk")

    # ── 9. 52-Week Position ────────────────────────────────────────────────────
    if current_price and week_52_high and week_52_high > 0:
        pct_from_high = ((week_52_high - current_price) / week_52_high) * 100
        if pct_from_high > 40:
            risks.append(f"Stock is {int(pct_from_high)}% below 52W high — significant correction underway")
        elif pct_from_high > 20:
            risks.append(f"Stock is {int(pct_from_high)}% below its 52W high — check if fundamentals warrant the drop")
        elif pct_from_high < 3:
            insights.append("Trading near 52-week high — strong sustained momentum")

    # ── Final Verdict ─────────────────────────────────────────────────────────
    if max_score == 0:
        verdict = "INSUFFICIENT DATA"
        verdict_color = "gray"
        summary = "Not enough financial data to generate a verdict. yfinance may be rate-limited — try refreshing in a few minutes."
    else:
        pct = (score / max_score) * 100
        if pct >= 75:
            verdict = "STRONG BUY"
            verdict_color = "green"
            summary = f"Exceptional fundamentals across valuation, profitability, growth, and safety. Score: {score}/{max_score} ({pct:.0f}%)."
        elif pct >= 60:
            verdict = "BUY"
            verdict_color = "lime"
            summary = f"Good quality business at a reasonable price. Worth accumulating on dips. Score: {score}/{max_score} ({pct:.0f}%)."
        elif pct >= 45:
            verdict = "HOLD"
            verdict_color = "yellow"
            summary = f"Decent business but mixed signals on valuation or growth. Hold existing positions. Score: {score}/{max_score} ({pct:.0f}%)."
        elif pct >= 28:
            verdict = "WEAK"
            verdict_color = "orange"
            summary = f"Multiple risk factors present. Exercise caution before adding exposure. Score: {score}/{max_score} ({pct:.0f}%)."
        else:
            verdict = "AVOID"
            verdict_color = "red"
            summary = f"Poor risk/reward. Financials or valuation do not support current price. Score: {score}/{max_score} ({pct:.0f}%)."

    if not insights:
        insights = ["Detailed financial data is being compiled. Check back shortly."]
    if not risks:
        risks = ["Standard market risks apply — please read our full disclaimer."]

    return {
        "verdict":       verdict,
        "verdict_color": verdict_color,
        "summary":       summary,
        "score":         score,
        "max_score":     max_score,
        "insights":      insights[:4],
        "risks":         risks[:3],
        "disclaimer":    (
            "This is a rule-based algorithmic assessment for educational purposes only. "
            "Not SEBI-registered investment advice. Do your own research before investing."
        ),
    }


if __name__ == "__main__":
    import json
    print("\n=== Searching 'reliance' ===")
    results = search_stocks("reliance")
    for r in results:
        print(f"  {r['symbol']} — {r['name']} ({r['sector']})")

    print("\n=== Fetching RELIANCE detail ===")
    detail = get_stock_detail("RELIANCE")
    print(json.dumps({
        "company_name": detail.get("company_name"),
        "current_price": detail.get("current_price"),
        "change_pct": detail.get("change_pct"),
        "fundamentals": detail.get("fundamentals"),
        "verdict": detail.get("analyst_verdict", {}).get("verdict"),
    }, indent=2, default=str))
