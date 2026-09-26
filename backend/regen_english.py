"""
Regenerate today's digest with English-only prompt + improved JSON parser.
Run from: f:\Stock market analysis\backend
"""
import sys
import io
import os

# Fix Windows console encoding for Unicode
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

os.chdir(r"F:\Stock market analysis\backend")
sys.path.insert(0, r"F:\Stock market analysis\backend")

from database import SessionLocal
from models import DailyDigest
from news_collector import collect_all_news
from ai_processor import process_news
from config import settings
from datetime import date

db = SessionLocal()
try:
    today = date.today()

    # Delete all of today's digests (including empty/stale ones)
    deleted = 0
    for d in db.query(DailyDigest).filter(DailyDigest.date == today).all():
        db.delete(d)
        deleted += 1
    db.commit()
    print(f"Deleted {deleted} existing digest(s) for {today}", flush=True)

    print("Collecting news...", flush=True)
    articles = collect_all_news(
        newsapi_key=settings.newsapi_key,
        gnews_api_key=settings.gnews_api_key,
    )
    print(f"Collected {len(articles)} articles", flush=True)

    print("Running Gemini 2.5 Flash (English-only, improved parser)...", flush=True)
    digest = process_news(articles, db)

    if digest:
        items = digest.items or []
        print(f"SUCCESS: {len(items)} items | mood={digest.market_mood}", flush=True)
        for i, item in enumerate(items[:5]):
            title = item.get("title", "")
            cat = item.get("category", "?")
            # Encode safely
            safe_title = title.encode('ascii', errors='replace').decode('ascii')
            print(f"  [{cat}] {safe_title[:70]}", flush=True)
        if len(items) > 0:
            print("Kepler Radar auto-generating in background...", flush=True)
        else:
            print("WARNING: 0 items generated", flush=True)
    else:
        print("Digest already exists or failed", flush=True)

finally:
    db.close()
    print("Done.", flush=True)
