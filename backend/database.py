"""
ANTIGRAVITY — Database Engine & Session Factory
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
    engine = create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=not settings.is_production,
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
