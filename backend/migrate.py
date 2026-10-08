"""
KEPLER -- Database Migration
Run this once on the production database to create all tables.

Usage:
    python migrate.py

Safe to run multiple times -- uses CREATE TABLE IF NOT EXISTS via SQLAlchemy,
and catches duplicate index errors gracefully.
"""
import sys
from loguru import logger


def run_migration():
    logger.info("Starting KEPLER database migration...")

    try:
        from database import engine
        from models import Base
        from sqlalchemy import inspect, text

        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # ── Create tables (IF NOT EXISTS is handled by SQLAlchemy) ────────────
        # We create tables one by one so a duplicate index on one table
        # doesn't abort the entire migration.
        for table in Base.metadata.sorted_tables:
            try:
                table.create(bind=engine, checkfirst=True)
                if table.name not in existing_tables:
                    logger.info(f"  Created table: {table.name}")
                else:
                    logger.info(f"  Table already exists (skipped): {table.name}")
            except Exception as table_err:
                logger.warning(f"  Skipped {table.name}: {table_err}")

        # ── Create indexes safely (skip if already exist) ─────────────────────
        from sqlalchemy.schema import CreateIndex
        from sqlalchemy import exc as sa_exc

        for table in Base.metadata.sorted_tables:
            for index in table.indexes:
                try:
                    with engine.begin() as conn:
                        conn.execute(CreateIndex(index))
                    logger.info(f"  Created index: {index.name}")
                except sa_exc.ProgrammingError as e:
                    if "already exists" in str(e) or "DuplicateTable" in str(e) or "duplicate" in str(e).lower():
                        logger.info(f"  Index already exists (skipped): {index.name}")
                    else:
                        logger.warning(f"  Index error for {index.name}: {e}")
                except Exception as e:
                    logger.warning(f"  Index error for {index.name}: {e}")

        # ── Final verification ─────────────────────────────────────────────────
        tables = sorted(inspect(engine).get_table_names())
        logger.success(f"Migration complete. {len(tables)} tables in database:")
        for t in tables:
            logger.info(f"  - {t}")

        # Verify required tables exist
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
