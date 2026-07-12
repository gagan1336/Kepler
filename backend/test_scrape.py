from news_collector import collect_all_news
from config import settings

print("Collecting news from all sources...")
print("=" * 70)
articles = collect_all_news(
    newsapi_key=settings.newsapi_key,
    gnews_api_key=settings.gnews_api_key,
)
print(f"\nTOTAL UNIQUE ARTICLES: {len(articles)}")
print("=" * 70)

# Group by source
from collections import defaultdict
by_source = defaultdict(list)
for a in articles:
    by_source[a["source"]].append(a)

print(f"\n{'SOURCE':<26} {'COUNT':>5}  {'PRIORITY':>8}")
print("-" * 45)
for src in sorted(by_source.keys(), key=lambda s: -by_source[s][0].get("priority", 5)):
    count = len(by_source[src])
    pri = by_source[src][0].get("priority", 5)
    print(f"  {src:<24} {count:>5}  {pri:>8}")

print(f"\n{'='*70}")
print("ALL ARTICLES (sorted by priority):")
print(f"{'='*70}")
sorted_articles = sorted(articles, key=lambda x: -x.get("priority", 5))
for i, a in enumerate(sorted_articles, 1):
    src = a["source"]
    pri = a.get("priority", 5)
    title = a["title"][:90]
    pub = a.get("published_at", "")[:16]
    print(f"\n{i:3}. [{src}] (priority={pri})")
    print(f"     TITLE: {title}")
    print(f"     DESC:  {a.get('description','')[:120]}")
    print(f"     DATE:  {pub}")
    print(f"     URL:   {a.get('url','')[:80]}")
