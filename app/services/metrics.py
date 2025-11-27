"""DB-only metrics recorder.

This module provides a small helper used by redirect handlers to record clicks
directly into the database from a background task. Design notes:

- We intentionally do NOT maintain per-request counters in Redis. Each redirect
    schedules a short background job that performs a single, idempotent SQL
    UPDATE to increment `click_count` and refresh `last_accessed_at`.
- Pros: correctness and simplicity (no aggregation edge-cases), immediate
    visibility in the DB and admin UI.
- Cons: higher write rate to the DB under heavy traffic. If you need higher
    throughput later, prefer a Redis INCR + periodic flush approach (batching
    reduces DB writes) or move metrics writes to a separate worker queue.

The implementation opens a fresh SQLAlchemy session so it doesn't depend on
the request-scoped session used by FastAPI endpoints.
"""

from app.db.Connection import database
from app.db.Models import models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def record_click(short_code: str):
        """Increment `click_count` and update `last_accessed_at` for the given short_code.

        This is a small, synchronous function intended to be scheduled via
        FastAPI's BackgroundTasks; it opens and closes its own DB session.
        """
        db = database.SessionLocal()
        try:
                updated = db.query(models.URLItem).filter(models.URLItem.short_code == short_code).update({
                        models.URLItem.click_count: models.URLItem.click_count + 1,
                        models.URLItem.last_accessed_at: datetime.utcnow()
                })
                db.commit()
                if updated:
                        logger.info("metrics.record_click: DB counters updated for %s", short_code)
        except Exception:
                logger.exception("metrics.record_click: failed to update DB for %s", short_code)
        finally:
                db.close()
