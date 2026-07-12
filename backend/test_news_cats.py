"""Quick test for news_live category fixes."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import news_live

# Clear cache and force fresh fetch
news_live._news_cache.clear()
result = news_live.get_live_news(limit=60, force_refresh=True)

cats = result['stats']['categories']
print("=== CATEGORY DISTRIBUTION ===")
for k, v in cats.items():
    print(f"  {k:10}: {v}")

print(f"\nTotal: {result['stats']['total']} | HIGH: {result['stats']['high_impact']}")

print("\n=== HIGH IMPACT ===")
for a in result['articles']:
    if a['impact'] == 'HIGH':
        t = a['title'][:65].encode('ascii', 'replace').decode()
        print(f"  {a['category']:8} | {t}")

print("\n=== GLOBAL ===")
for a in result['articles']:
    if a['category'] == 'GLOBAL':
        t = a['title'][:65].encode('ascii', 'replace').decode()
        print(f"  {a['impact']:6} | {t}")

print("\n=== STOCKS ===")
for a in result['articles']:
    if a['category'] == 'STOCKS':
        t = a['title'][:65].encode('ascii', 'replace').decode()
        print(f"  {a['impact']:6} | {t}")

print("\nDONE")
