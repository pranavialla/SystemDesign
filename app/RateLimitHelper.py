import logging
from app.core.logging_config import configure_logging
from app.db.Connection import database
from fastapi import Request
import redis.exceptions

logger = configure_logging()
RATE_LIMIT_DEFAULT_LIMIT = 100
RATE_LIMIT_DEFAULT_WINDOW = 60 
RATE_LIMIT_VALUE_KEY = "config:RATE_LIMIT_LIMIT"
RATE_LIMIT_WINDOW_KEY = "config:RATE_LIMIT_WINDOW"

def get_rate_limit_config(database):
    limit, window = RATE_LIMIT_DEFAULT_LIMIT, RATE_LIMIT_DEFAULT_WINDOW
    try:
        limit_str = database.redis_client.get(RATE_LIMIT_VALUE_KEY)
        window_str = database.redis_client.get(RATE_LIMIT_WINDOW_KEY)
        limit = int(limit_str) if limit_str else limit
        window = int(window_str) if window_str else window
    except (redis.exceptions.ConnectionError, ValueError):
        logger.warning(
            f"Failed to fetch/parse dynamic rate limit config. "
            f"Using defaults: {limit} requests per {window} seconds."
        )
    return limit, window


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_admin_path(path: str) -> bool:
    return path.startswith("/admin") or path.startswith("/api/v1/admin")


def check_rate_limit(database, key: str, limit: int, window: int):
    try:
        database.redis_client.ping()
        current = database.redis_client.get(key)
    except redis.exceptions.ConnectionError:
        logger.warning("Redis connection failed. Rate limiting skipped (fail open).")
        return None  # Skip rate limiting if Redis is down

    if current and int(current) >= limit:
        return False  # Limit exceeded

    pipe = database.redis_client.pipeline()
    pipe.incr(key, 1)
    if not current:
        pipe.expire(key, window)
    pipe.execute()
    return True
