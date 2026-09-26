from database import SessionLocal
from news_collector import collect_all_news
from ai_processor import process_news
from config import settings

print(f'Key: {settings.gemini_api_key[:12]}...')

db = SessionLocal()
try:
    print('Step 1: Collecting news from RSS feeds...')
    articles = collect_all_news(
        newsapi_key=settings.newsapi_key,
        gnews_api_key=settings.gnews_api_key,
    )
    print(f'Step 1 done: {len(articles)} articles')

    print('Step 2: Gemini 2.5 Flash processing...')
    digest = process_news(articles, db)

    if digest:
        print(f'Step 2 done: {len(digest.items)} items, mood={digest.market_mood}')
        if digest.items:
            print('Top 3 items:')
            for item in digest.items[:3]:
                cat = item.get("category", "?")
                title = item.get("title", "")[:70]
                print(f'  [{cat}] {title}')
            print('Kepler Radar now generating in background...')
        else:
            print('WARNING: 0 items - Gemini returned empty')
    else:
        print('Skipped: digest already exists for today')
finally:
    db.close()
