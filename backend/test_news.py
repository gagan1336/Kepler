import time, json
from news_live import fetch_all_news, get_live_news, FEEDS
import news_live

print("Testing news_live module...")
orig = news_live.FEEDS
news_live.FEEDS = orig[:4]

t = time.time()
arts = fetch_all_news(force=True)
elapsed = round(time.time()-t, 1)

print(f"Got {len(arts)} articles in {elapsed}s")
high = [a for a in arts if a['impact'] == 'HIGH']
mid  = [a for a in arts if a['impact'] == 'MEDIUM']
print(f"HIGH={len(high)} MEDIUM={len(mid)} LOW={len(arts)-len(high)-len(mid)}")

cats = {}
for a in arts:
    cats[a['category']] = cats.get(a['category'], 0) + 1
print("Categories:", cats)

for a in arts[:8]:
    print(f"  [{a['impact']:6}] [{a['category']:8}] {a['source'][:22]:22}  {a['title'][:55]}")

news_live.FEEDS = orig

print("\nJSON serialization test...")
result = get_live_news(limit=5)
json.dumps(result)
print(f"OK - {result['count']} articles, {result['stats']['high_impact']} HIGH impact")
