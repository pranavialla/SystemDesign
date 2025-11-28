from app.db.Connection import database
from app.db import repository
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def record_click(short_code: str):
        db = database.SessionLocal()
        try:
                updated = repository.increment_click(db, short_code)
                if updated:
                        logger.info("metrics.record_click: DB counters updated for %s", short_code)
        except Exception:
                logger.exception("metrics.record_click: failed to update DB for %s", short_code)
        finally:
                db.close()

def update_stat(request ,background_tasks, short_code):
    if not getattr(request.state, "metrics_scheduled", False):
        xff = request.headers.get("x-forwarded-for")
        background_tasks.add_task(record_click, short_code)
        if xff:
            client_ip = xff.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        request.state.metrics_scheduled = True
