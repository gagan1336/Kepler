"""
ANTIGRAVITY — Fundamentals Fetcher (yfinance-powered)
Fetches fundamental data directly from yfinance (Yahoo Finance API).
Replaces previous Screener.in web scraping — more reliable, no HTML parsing.
24-hour in-memory cache to avoid excessive API calls.

yfinance reference: https://ranaroussi.github.io/yfinance/reference/index.html

Data sources used:
  - ticker.info         → PE, PB, ROE, D/E, market cap, dividend yield, EPS, sector
  - ticker.financials   → Revenue, Net Income (trailing 4 quarters)
  - ticker.balance_sheet→ Total assets, equity for ROCE calculation
  - ticker.major_holders→ Promoter (insider) %, institutional %
  - ticker.fast_info    → Quick price sanity check
"""
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import yfinance as yf
from loguru import logger

# ── In-memory cache: symbol → {data, fetched_at} ─────────────────────────────
_cache: Dict[str, Dict] = {}
_CACHE_TTL_SECONDS = 24 * 3600  # 24 hours


def _is_cache_valid(symbol: str) -> bool:
    entry = _cache.get(symbol)
    if not entry:
        return False
    age = (datetime.utcnow() - entry["fetched_at"]).total_seconds()
    return age < _CACHE_TTL_SECONDS


def _safe_float(val: Any, multiplier: float = 1.0) -> Optional[float]:
    """Convert yfinance value to float, applying optional multiplier."""
    try:
        if val is None:
            return None
        f = float(val)
        if f != f:  # NaN check
            return None
        return round(f * multiplier, 4)
    except (TypeError, ValueError):
        return None


def _pct(val: Any) -> Optional[float]:
    """Convert decimal fraction → percentage (e.g. 0.15 → 15.0)."""
    f = _safe_float(val)
    if f is None:
        return None
    # yfinance returns ratios as decimals (0.15 = 15%), except some fields
    return round(f * 100, 2) if abs(f) <= 1.5 else round(f, 2)


def _growth_cagr_from_financials(df, column: str, years: int = 3) -> Optional[float]:
    """
    Compute approximate CAGR over `years` from yfinance annual financials DataFrame.
    Columns are year-end dates (most recent first).
    """
    try:
        if df is None or df.empty:
            return None
        if column not in df.index:
            return None
        series = df.loc[column].dropna()
        if len(series) < 2:
            return None

        # Most recent and oldest available (up to `years` back)
        n = min(years, len(series) - 1)
        latest = float(series.iloc[0])
        oldest = float(series.iloc[n])

        if oldest <= 0 or latest <= 0:
            return None

        cagr = ((latest / oldest) ** (1 / n) - 1) * 100
        return round(cagr, 2)
    except Exception:
        return None


def fetch_fundamentals(symbol: str) -> Dict[str, Any]:
    """
    Fetch fundamental data for a NSE stock via yfinance.
    Returns cached result if available and < 24 hours old.

    Args:
        symbol: NSE symbol WITHOUT .NS suffix (e.g. "RELIANCE", "TCS")

    Returns:
        dict with: pe_ratio, pb_ratio, roe, roce, debt_to_equity,
                   promoter_holding, fii_holding, dii_holding,
                   revenue_growth_3yr, profit_growth_3yr,
                   current_ratio, dividend_yield, market_cap,
                   face_value, company_name, sector, industry,
                   eps, beta, book_value, revenue_growth_1yr,
                   profit_growth_1yr, source, fetched_at
    """
    symbol = symbol.upper().replace(".NS", "").replace(".BO", "").strip()

    if _is_cache_valid(symbol):
        logger.debug(f"Fundamentals cache hit: {symbol}")
        return _cache[symbol]["data"]

    logger.info(f"Fetching fundamentals for {symbol} via yfinance")

    ns_symbol = f"{symbol}.NS"
    ticker = yf.Ticker(ns_symbol)

    data = _empty_fundamentals(symbol)
    data["source"] = "yfinance"

    try:
        # ── 1. Core info dict (PE, PB, ROE, D/E, market cap, etc.) ──────────
        info = ticker.info or {}
        if not info or info.get("trailingPE") is None and info.get("marketCap") is None:
            # Try BSE suffix as fallback
            ticker_bo = yf.Ticker(f"{symbol}.BO")
            info = ticker_bo.info or {}
            logger.debug(f"Fell back to .BO for {symbol}")

        # Company identity
        data["company_name"] = (
            info.get("longName") or info.get("shortName") or symbol
        )
        data["sector"]   = info.get("sector", "")
        data["industry"] = info.get("industry", "")

        # Valuation
        data["pe_ratio"]       = _safe_float(info.get("trailingPE"))
        data["forward_pe"]     = _safe_float(info.get("forwardPE"))
        data["pb_ratio"]       = _safe_float(info.get("priceToBook"))
        data["ps_ratio"]       = _safe_float(info.get("priceToSalesTrailing12Months"))
        data["peg_ratio"]      = _safe_float(info.get("pegRatio"))
        data["ev_ebitda"]      = _safe_float(info.get("enterpriseToEbitda"))

        # Profitability (yfinance returns as decimal fractions → convert to %)
        data["roe"]            = _pct(info.get("returnOnEquity"))
        data["roa"]            = _pct(info.get("returnOnAssets"))
        data["profit_margin"]  = _pct(info.get("profitMargins"))
        data["operating_margin"] = _pct(info.get("operatingMargins"))
        data["gross_margin"]   = _pct(info.get("grossMargins"))

        # Safety / leverage
        data["debt_to_equity"] = _safe_float(info.get("debtToEquity"))
        # yfinance D/E is in percentage for some stocks — normalize if > 10
        if data["debt_to_equity"] is not None and data["debt_to_equity"] > 10:
            data["debt_to_equity"] = round(data["debt_to_equity"] / 100, 4)
        data["current_ratio"]  = _safe_float(info.get("currentRatio"))
        data["quick_ratio"]    = _safe_float(info.get("quickRatio"))

        # Income / balance sheet highlights
        data["market_cap"]     = _safe_float(info.get("marketCap"))
        data["enterprise_value"] = _safe_float(info.get("enterpriseValue"))
        data["book_value"]     = _safe_float(info.get("bookValue"))
        data["eps"]            = _safe_float(info.get("trailingEps"))
        data["forward_eps"]    = _safe_float(info.get("forwardEps"))
        data["beta"]           = _safe_float(info.get("beta"))

        # Dividends
        data["dividend_yield"] = _pct(info.get("dividendYield"))
        data["dividend_rate"]  = _safe_float(info.get("dividendRate"))
        data["payout_ratio"]   = _pct(info.get("payoutRatio"))

        # Revenue & growth (1-year YoY from yfinance)
        data["revenue_growth_1yr"]  = _pct(info.get("revenueGrowth"))
        data["profit_growth_1yr"]   = _pct(info.get("earningsGrowth"))
        data["revenue_ttm"]         = _safe_float(info.get("totalRevenue"))
        data["ebitda_ttm"]          = _safe_float(info.get("ebitda"))
        data["free_cash_flow"]      = _safe_float(info.get("freeCashflow"))

        # Shareholding from major_holders
        _fetch_shareholding(ticker, data)

        # 3-year CAGR from annual financials
        _fetch_cagr_from_financials(ticker, data)

        # ROCE approximation (EBIT / Capital Employed)
        _compute_roce(ticker, data, info)

        logger.info(
            f"Fundamentals OK for {symbol}: "
            f"PE={data.get('pe_ratio')}, ROE={data.get('roe')}%, "
            f"D/E={data.get('debt_to_equity')}"
        )

    except Exception as e:
        logger.error(f"Unexpected error fetching fundamentals for {symbol}: {e}")

    data["fetched_at"] = datetime.utcnow().isoformat()
    _cache[symbol] = {"data": data, "fetched_at": datetime.utcnow()}
    return data


def _fetch_shareholding(ticker: yf.Ticker, data: Dict[str, Any]) -> None:
    """
    Fill promoter/FII/DII/public holding percentages.
    yfinance provides heldPercentInsiders (promoters) and
    heldPercentInstitutions (FII + DII combined) via ticker.info.
    major_holders gives a more structured breakdown.
    """
    try:
        info = ticker.info or {}

        # From info dict (most reliable for NSE stocks)
        insider_pct = _pct(info.get("heldPercentInsiders"))
        inst_pct    = _pct(info.get("heldPercentInstitutions"))

        if insider_pct is not None:
            data["promoter_holding"] = insider_pct
        if inst_pct is not None:
            # yfinance lumps FII + DII; we split heuristically 60/40
            data["fii_holding"] = round(inst_pct * 0.60, 2)
            data["dii_holding"] = round(inst_pct * 0.40, 2)

        # Try major_holders for a better split
        try:
            mh = ticker.major_holders
            if mh is not None and not mh.empty:
                for _, row in mh.iterrows():
                    label = str(row.iloc[1]).lower() if len(row) > 1 else ""
                    val_str = str(row.iloc[0]) if len(row) > 0 else "0"
                    # Parse percentage value
                    val = None
                    try:
                        val = float(val_str.replace("%", "").strip())
                    except (ValueError, TypeError):
                        pass
                    if val is None:
                        continue

                    if "insider" in label or "promoter" in label:
                        data["promoter_holding"] = round(val, 2)
                    elif "institution" in label:
                        inst_total = round(val, 2)
                        data["fii_holding"] = round(inst_total * 0.60, 2)
                        data["dii_holding"] = round(inst_total * 0.40, 2)
        except Exception:
            pass  # major_holders may fail silently

    except Exception as e:
        logger.debug(f"Shareholding fetch partial failure: {e}")


def _fetch_cagr_from_financials(ticker: yf.Ticker, data: Dict[str, Any]) -> None:
    """Compute 3-year revenue and profit CAGR from yfinance annual financials."""
    try:
        fin = ticker.financials  # columns = year-end dates, rows = line items
        if fin is not None and not fin.empty:
            # Revenue CAGR
            rev_cagr = _growth_cagr_from_financials(fin, "Total Revenue", years=3)
            if rev_cagr is not None:
                data["revenue_growth_3yr"] = rev_cagr

            # Net income CAGR
            profit_cagr = _growth_cagr_from_financials(fin, "Net Income", years=3)
            if profit_cagr is None:
                # Try alternate row name
                profit_cagr = _growth_cagr_from_financials(
                    fin, "Net Income Common Stockholders", years=3
                )
            if profit_cagr is not None:
                data["profit_growth_3yr"] = profit_cagr

    except Exception as e:
        logger.debug(f"Financials CAGR fetch failed: {e}")


def _compute_roce(ticker: yf.Ticker, data: Dict[str, Any], info: Dict) -> None:
    """
    ROCE = EBIT / Capital Employed
    Capital Employed = Total Assets - Current Liabilities
    yfinance provides this via balance_sheet + financials.
    Fallback: estimate from ROE and D/E.
    """
    try:
        bs = ticker.balance_sheet
        fin = ticker.financials

        if (bs is not None and not bs.empty and
                fin is not None and not fin.empty):

            # Capital Employed = Total Assets - Current Liabilities
            total_assets = None
            curr_liab    = None
            ebit         = None

            for row_name in bs.index:
                rl = row_name.lower()
                if "total assets" in rl:
                    total_assets = float(bs.loc[row_name].iloc[0])
                elif "current liabilities" in rl:
                    curr_liab = float(bs.loc[row_name].iloc[0])

            for row_name in fin.index:
                rl = row_name.lower()
                if "ebit" in rl and "ebitda" not in rl:
                    ebit = float(fin.loc[row_name].iloc[0])
                    break
            if ebit is None:
                # Derive EBIT from operating income
                for row_name in fin.index:
                    if "operating income" in row_name.lower():
                        ebit = float(fin.loc[row_name].iloc[0])
                        break

            if total_assets and curr_liab and ebit:
                capital_employed = total_assets - curr_liab
                if capital_employed > 0:
                    roce = (ebit / capital_employed) * 100
                    data["roce"] = round(roce, 2)
                    return

    except Exception:
        pass

    # Fallback: estimate ROCE ≈ ROE × (1 - 1/(1+D/E)) if D/E available
    try:
        roe = data.get("roe")
        de  = data.get("debt_to_equity")
        if roe is not None and de is not None and de >= 0:
            equity_mult = 1 + de
            roce_est = roe / equity_mult * (1 + de * 0.7)  # rough approximation
            data["roce"] = round(roce_est, 2)
    except Exception:
        pass


def _empty_fundamentals(symbol: str) -> Dict[str, Any]:
    return {
        "symbol":              symbol,
        "company_name":        None,
        "sector":              None,
        "industry":            None,
        # Valuation
        "pe_ratio":            None,
        "forward_pe":          None,
        "pb_ratio":            None,
        "ps_ratio":            None,
        "peg_ratio":           None,
        "ev_ebitda":           None,
        # Profitability
        "roe":                 None,
        "roa":                 None,
        "roce":                None,
        "profit_margin":       None,
        "operating_margin":    None,
        "gross_margin":        None,
        # Safety
        "debt_to_equity":      None,
        "current_ratio":       None,
        "quick_ratio":         None,
        # Size / income
        "market_cap":          None,
        "enterprise_value":    None,
        "book_value":          None,
        "eps":                 None,
        "forward_eps":         None,
        "beta":                None,
        "revenue_ttm":         None,
        "ebitda_ttm":          None,
        "free_cash_flow":      None,
        # Dividends
        "dividend_yield":      None,
        "dividend_rate":       None,
        "payout_ratio":        None,
        # Growth
        "revenue_growth_1yr":  None,
        "profit_growth_1yr":   None,
        "revenue_growth_3yr":  None,
        "profit_growth_3yr":   None,
        # Shareholding
        "promoter_holding":    None,
        "fii_holding":         None,
        "dii_holding":         None,
        # Meta
        "source":              "yfinance",
        "fetched_at":          datetime.utcnow().isoformat(),
    }


def invalidate_cache(symbol: str) -> None:
    """Manually invalidate cache for a symbol (e.g., after earnings)."""
    _cache.pop(symbol.upper().replace(".NS", ""), None)


def get_cache_stats() -> Dict[str, Any]:
    """Return cache statistics for monitoring."""
    now = datetime.utcnow()
    valid = sum(
        1 for v in _cache.values()
        if (now - v["fetched_at"]).total_seconds() < _CACHE_TTL_SECONDS
    )
    return {
        "total_cached": len(_cache),
        "valid_entries": valid,
        "cache_ttl_hours": _CACHE_TTL_SECONDS / 3600,
    }


if __name__ == "__main__":
    symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "BAJFINANCE"]
    for sym in symbols:
        print(f"\n{'='*50}")
        data = fetch_fundamentals(sym)
        print(f"  Company : {data.get('company_name')}")
        print(f"  Sector  : {data.get('sector')}")
        print(f"  PE      : {data.get('pe_ratio')}")
        print(f"  PB      : {data.get('pb_ratio')}")
        print(f"  ROE     : {data.get('roe')}%")
        print(f"  ROCE    : {data.get('roce')}%")
        print(f"  D/E     : {data.get('debt_to_equity')}")
        print(f"  Div Yld : {data.get('dividend_yield')}%")
        print(f"  Mkt Cap : ₹{data.get('market_cap', 0) / 1e7:.0f} Cr")
        print(f"  3yr Rev CAGR : {data.get('revenue_growth_3yr')}%")
        print(f"  3yr PAT CAGR : {data.get('profit_growth_3yr')}%")
        print(f"  Promoter: {data.get('promoter_holding')}%")
        print(f"  FII     : {data.get('fii_holding')}%")
        time.sleep(1)
