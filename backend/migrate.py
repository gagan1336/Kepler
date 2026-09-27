"""
KEPLER -- Database Migration
Run this once on the production database to create all tables.

Usage:
    python migrate.py

Safe to run multiple times -- uses CREATE TABLE IF NOT EXISTS via SQLAlchemy.
"""
import sys
from loguru import logger


def run_migration():
    logger.info("Starting KEPLER database migration...")

    try:
        from database import engine
        from models import Base

        # Create all tables defined in models.py
        # SQLAlchemy uses IF NOT EXISTS internally -- safe to re-run
        Base.metadata.create_all(bind=engine)

        # List all tables that now exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = sorted(inspector.get_table_names())

        logger.success(f"Migration complete. {len(tables)} tables in database:")
        for t in tables:
            logger.info(f"  - {t}")

        # Verify new security tables exist
        required = {"ai_quotas", "audit_logs", "push_tokens"}
        missing = required - set(tables)
        if missing:
            logger.error(f"MISSING TABLES: {missing}")
            sys.exit(1)
        else:
            logger.success("All required tables present: ai_quotas, audit_logs, push_tokens")

    except Exception as e:
        logger.error(f"Migration FAILED: {e}")
        raise


if __name__ == "__main__":
    run_migration()
