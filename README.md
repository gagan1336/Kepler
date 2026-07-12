# ANTIGRAVITY — AI Market Intelligence Platform

> AI-powered market intelligence for Indian traders and investors.
> Daily AI-curated news, breakout scanner, sector analysis, IPO briefs. No tips. No noise. Just research.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), Tailwind CSS v3 |
| Backend | Python FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL (Railway hosted) |
| AI | Google Gemini 1.5 Pro + Flash |
| Market Data | yfinance, nsetools, feedparser |
| News | NewsAPI.org, GNews API, RSS feeds |
| Payments | Razorpay (subscriptions) |
| Email | Resend API |
| Alerts | Telegram Bot API |
| Hosting | Vercel (frontend) + Railway (backend + DB) |

---

## Project Structure

```
antigravity/
├── backend/
│   ├── main.py               # FastAPI app + all endpoints
│   ├── models.py             # SQLAlchemy ORM models
│   ├── database.py           # Engine + session factory
│   ├── config.py             # Pydantic settings
│   ├── auth.py               # JWT auth + Google OAuth
│   ├── news_collector.py     # RSS + NewsAPI + GNews
│   ├── ai_processor.py       # Gemini 1.5 Pro digest pipeline
│   ├── breakout_scanner.py   # Nifty 500 technical scanner
│   ├── sector_analyzer.py    # Weekly sector report
│   ├── fundamentals_fetcher.py  # Screener.in scraper
│   ├── ipo_analyzer.py       # IPO brief generator
│   ├── telegram_publisher.py # Telegram channel publisher
│   ├── email_service.py      # Resend email sequences
│   ├── scheduler.py          # APScheduler jobs
│   ├── alembic/              # DB migrations
│   ├── requirements.txt
│   ├── Procfile              # Railway deployment
│   └── .env.example
└── frontend/
    ├── app/
    │   ├── page.tsx          # Homepage (10 sections)
    │   ├── dashboard/        # Protected dashboard
    │   ├── pricing/          # Pricing + FAQ
    │   ├── sample/           # Public sample content
    │   ├── about/            # About + disclaimer
    │   ├── login/            # Auth pages
    │   └── register/
    ├── components/
    │   ├── Navbar.tsx
    │   ├── Footer.tsx
    │   ├── DigestCard.tsx
    │   ├── BreakoutTable.tsx
    │   ├── SectorReport.tsx
    │   ├── PricingCard.tsx
    │   ├── TradingViewWidget.tsx
    │   └── Disclaimer.tsx
    ├── lib/
    │   ├── api.ts            # All API calls
    │   └── auth.ts           # Auth context
    └── .env.example
```

---

## Setup & Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- PostgreSQL database (Railway recommended)

### 1. Clone and set up backend

```bash
git clone https://github.com/yourusername/antigravity
cd antigravity/backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
copy .env.example .env
# Edit .env with your API keys
```

### 2. Set up database

```bash
# Run migrations (requires PostgreSQL running and DATABASE_URL set in .env)
alembic upgrade head
```

### 3. Start backend

```bash
uvicorn main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

### 4. Set up frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Copy and fill in environment variables
copy .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000

# Start dev server
npm run dev
# App at http://localhost:3000
```

---

## API Keys — Where to Get Them

### Required

| Key | Where to Get | Free Tier |
|---|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) | Yes — generous |
| `DATABASE_URL` | [railway.app](https://railway.app) — create PostgreSQL service | Yes — $5 credit |
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` | N/A |

### News APIs (optional but recommended)

| Key | Where to Get | Free Tier |
|---|---|---|
| `NEWSAPI_KEY` | [newsapi.org/register](https://newsapi.org/register) | 100 req/day |
| `GNEWS_API_KEY` | [gnews.io](https://gnews.io) | 100 req/day |

> RSS feeds work with zero API keys. NewsAPI and GNews add more coverage.

### Payments

| Key | Where to Get |
|---|---|
| `RAZORPAY_KEY_ID` | [dashboard.razorpay.com](https://dashboard.razorpay.com/app/keys) |
| `RAZORPAY_KEY_SECRET` | Same page |
| `RAZORPAY_WEBHOOK_SECRET` | Dashboard → Webhooks → Create → copy secret |

**Razorpay webhook URL:** `https://your-backend.railway.app/webhooks/razorpay`

### Telegram

1. Create a bot: Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Copy the token → `TELEGRAM_BOT_TOKEN`
3. Create two private channels (Pro and Elite)
4. Add your bot as admin to both channels
5. Get channel IDs: add [@username_to_id_bot](https://t.me/username_to_id_bot) to each channel
6. Get your personal ID: message [@userinfobot](https://t.me/userinfobot)

### Email

| Key | Where to Get | Free Tier |
|---|---|---|
| `RESEND_API_KEY` | [resend.com/api-keys](https://resend.com/api-keys) | 3,000 emails/month |

---

## Deployment

### Deploy Backend to Railway

1. Go to [railway.app](https://railway.app) and create a new project
2. Add a PostgreSQL database service
3. Add a new service from GitHub (connect your repo)
4. Set the root directory to `backend/`
5. Railway auto-detects the `Procfile`
6. Add all environment variables in the Railway dashboard
7. Run migrations: `railway run alembic upgrade head`

### Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) and import your GitHub repo
2. Set root directory to `frontend/`
3. Add environment variables:
   - `NEXT_PUBLIC_API_URL` = your Railway backend URL
   - `NEXT_PUBLIC_RAZORPAY_KEY_ID` = your Razorpay key
4. Deploy

---

## Razorpay Plans Setup

The 4 subscription plans are **automatically created** when the FastAPI backend starts up (in the `startup_event` function). You don't need to create them manually.

Plans created:
- `ANTIGRAVITY_PRO_MONTHLY`: ₹799/month
- `ANTIGRAVITY_PRO_ANNUAL`: ₹7,499/year
- `ANTIGRAVITY_ELITE_MONTHLY`: ₹1,999/month
- `ANTIGRAVITY_ELITE_ANNUAL`: ₹17,999/year

**Test mode:** Use Razorpay test keys during development. Switch to live keys before going live.

---

## Scheduler Jobs (Production Times)

| Job | Time (IST) |
|---|---|
| News collection + AI processing | Mon–Fri 6:00 AM |
| Breakout scanner | Mon–Fri 7:00 AM |
| Telegram morning digest | Mon–Fri 8:00 AM |
| Sector analyzer | Every Tuesday 7:30 AM |
| Email sequences | Daily 9:00 AM |
| Log cleanup | Daily 11:00 PM |

The scheduler runs as part of the FastAPI process. On Railway, it starts automatically with the web service.

---

## Running the Pipeline Manually

```bash
cd backend
source venv/bin/activate

# Collect and process news
python -c "
from database import SessionLocal
from news_collector import collect_all_news
from ai_processor import process_news
from config import settings
db = SessionLocal()
articles = collect_all_news(settings.newsapi_key, settings.gnews_api_key)
digest = process_news(articles, db)
print(f'Digest: {len(digest.items)} items')
db.close()
"

# Run breakout scanner (test mode — first 20 stocks)
python -c "
from database import SessionLocal
from breakout_scanner import scan_breakouts
db = SessionLocal()
results = scan_breakouts(db, test_mode=True)
print(f'Found: {len(results)} setups')
db.close()
"

# Generate sector report
python -c "
from database import SessionLocal
from sector_analyzer import generate_sector_report
db = SessionLocal()
report = generate_sector_report(db)
print(report.sector_name if report else 'No report')
db.close()
"
```

---

## Legal Notes

- This platform is not SEBI registered
- All content is for educational purposes only
- The SEBI disclaimer appears on every page, every Telegram message, every report
- Words like "buy", "sell", "target price", "guaranteed" are never used anywhere in the codebase
- The AI prompts are specifically instructed to avoid these words

---

## Support

Email: hello@antigravity.in
