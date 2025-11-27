from app.db.Connection import database
from app.db.Models import models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def record_click(short_code: str):
    """Synchronous helper used by background tasks: increment Redis metric and update DB counters."""
    try:
        # Redis metric increment (fast)
        database.redis_client.incr(f"metrics:clicks:{short_code}")
    except Exception:
        logger.debug("Failed to increment Redis metric for %s", short_code)

    # Update DB using a fresh session to avoid touching request session
    db = database.SessionLocal()
    try:
        db.query(models.URLItem).filter(models.URLItem.short_code == short_code).update({
            models.URLItem.click_count: models.URLItem.click_count + 1,
            models.URLItem.last_accessed_at: datetime.utcnow()
        })
        db.commit()
    except Exception:
        logger.exception("Failed to update DB counters for %s", short_code)
    finally:
        db.close()
