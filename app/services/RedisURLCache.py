from urllib.request import Request
from venv import logger
import redis.exceptions
from app.db.Connection import database
from app.db.Models.models import URLItem


CACHE_TTL = 86400

@staticmethod
def get(short_code: str, request: Request):
    cached_url = database.redis_client.get(f"url:{short_code}")
    if cached_url:
        try:
            cached_decoded = cached_url.decode() if isinstance(cached_url, (bytes, bytearray)) else str(cached_url)
        except Exception:
            cached_decoded = str(cached_url)

        logger.info(f"Redirect cache HIT for {short_code} -> {cached_decoded}")
        return cached_decoded
    
@staticmethod
def put(short_code: str, db_url: URLItem ):
    try:
        database.redis_client.setex(f"url:{short_code}", CACHE_TTL, db_url.original_url)
        logger.debug(f"Cached {short_code} -> {db_url.original_url[:50]}")
    except redis.exceptions.ConnectionError:
        logger.warning(f"Failed to cache {short_code}, Redis unavailable")