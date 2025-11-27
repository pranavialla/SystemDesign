from app.db.Connection import database
from datetime import datetime
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def record_click(short_code: str, client_ip: Optional[str] = None):
    """Record a click in Redis with idempotency using client IP and a short time window.

    This creates a dedupe key per (short_code, client_ip, second) so repeated calls
    within the same second from the same client won't double-count.
    """
    if client_ip is None:
        client_ip = "unknown"

    window = int(time.time())
    dedupe_key = f"metrics:dedup:{short_code}:{client_ip}:{window}"
    try:
        created = database.redis_client.set(dedupe_key, 1, nx=True, ex=2)
        if not created:
            logger.debug("metrics.record_click: duplicate within window skipped %s", dedupe_key)
            return

        logger.info("metrics.record_click: recording click for %s from %s", short_code, client_ip)
        database.redis_client.incr(f"metrics:clicks:{short_code}")
    except Exception:
        logger.exception("metrics.record_click failed for %s from %s", short_code, client_ip)
