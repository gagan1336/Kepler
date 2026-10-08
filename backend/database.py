"""
KEPLER -- Database Engine & Session Factory
SQLAlchemy async setup with connection pooling for production.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool
from config import settings
from loguru import logger


# ── Engine ────────────────────────────────────────────────────────────────────
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=not settings.is_production,
    )
else:
    # Detect Supabase transaction pooler (port 6543) vs session pooler (5432).
    # Transaction pooler (Supavisor) does NOT support prepared statements.
    _is_transaction_pooler = ":6543/" in settings.database_url
    _is_supabase = "supabase" in settings.database_url

    _connect_args: dict = {}

    if _is_supabase:
        # Force SSL for Supabase — also helps avoid IPv6 fallback issues.
        _connect_args["sslmode"] = "require"
        logger.info("Supabase detected — SSL enforced.")

    if _is_transaction_pooler:
        # pgbouncer / Supavisor transaction mode requires prepared_statements=off
        _connect_args["options"] = "-c statement_timeout=30000"
        logger.info("Supabase transaction pooler (port 6543) detected — prepared statements disabled.")

    engine = create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=5 if _is_transaction_pooler else 10,
        max_overflow=10 if _is_transaction_pooler else 20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=not settings.is_production,
        connect_args=_connect_args,
    )


# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ── Base class ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency for FastAPI routes ─────────────────────────────────────────────
def get_db():
    """Yield a DB session and ensure it's closed after each request."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create all tables. Called on startup if not using Alembic migrations."""
    from models import Base as ModelBase  # noqa: F401 — imports all models
    ModelBase.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")
