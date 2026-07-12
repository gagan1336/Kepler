"""Quick test for the new yfinance-powered fundamentals fetcher."""
import sys
sys.path.insert(0, r'f:\Stock market analysis\backend')

from fundamentals_fetcher import fetch_fundamentals, get_cache_stats

print("=== Testing fundamentals_fetcher.py ===")
data = fetch_fundamentals('TCS')

print(f"Symbol  : {data['symbol']}")
print(f"Company : {data['company_name']}")
print(f"Sector  : {data['sector']}")
print(f"Source  : {data['source']}")
print()
print(f"PE Ratio: {data['pe_ratio']}")
print(f"ROE     : {data['roe']}%")
print(f"ROCE    : {data['roce']}%")
print(f"D/E     : {data['debt_to_equity']}")
print(f"Profit Margin: {data['profit_margin']}%")
print(f"Op Margin: {data['operating_margin']}%")
print()
print(f"Revenue Growth 1Y: {data['revenue_growth_1yr']}%")
print(f"Revenue Growth 3Y: {data['revenue_growth_3yr']}%")
print(f"Profit Growth 3Y : {data['profit_growth_3yr']}%")
print()
print(f"Promoter: {data['promoter_holding']}%")
print(f"FII     : {data['fii_holding']}%")
print(f"DII     : {data['dii_holding']}%")
print()
print("Cache stats:", get_cache_stats())
print("=== PASS ===")
