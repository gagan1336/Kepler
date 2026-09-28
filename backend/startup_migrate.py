"""Auto-migration script -- runs on every deploy before uvicorn starts."""
import sys
from loguru import logger

def auto_migrate():
    try:
        from database import engine
        from models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("DB auto-migration complete")
    except Exception as e:
        logger.error(f"DB auto-migration FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    auto_migrate()