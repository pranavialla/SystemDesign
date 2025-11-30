from urllib.request import Request
import logging
import redis.exceptions
from app.db.Connection import database
from app.db.Models.models import URLItem
from app.utils.encoding import normalize_short_code

logger = logging.getLogger(__name__)
CACHE_TTL = 86400

@staticmethod
def get(short_code: str, request: Request):
    normalized = normalize_short_code(short_code)
    cache_key = f"url:{normalized}"
    
    try:
        cached_url = database.redis_client.get(cache_key)
    except redis.exceptions.ConnectionError:
        logger.warning(f"Redis connection failed for {short_code}")
        return None
    
    if cached_url:
        try:
            cached_decoded = cached_url.decode() if isinstance(cached_url, (bytes, bytearray)) else str(cached_url)
        except Exception:
            cached_decoded = str(cached_url)

        logger.info(f"Redirect cache HIT for {short_code} -> {cached_decoded}")
        return cached_decoded
    
    return None
    
@staticmethod
def put(short_code: str, db_url: URLItem):
    normalized = normalize_short_code(short_code)
    cache_key = f"url:{normalized}"
    
    try:
        database.redis_client.setex(cache_key, CACHE_TTL, db_url.original_url)
        logger.debug(f"Cached {short_code} -> {db_url.original_url[:50]}")
    except redis.exceptions.ConnectionError:
        logger.warning(f"Failed to cache {short_code}, Redis unavailable")