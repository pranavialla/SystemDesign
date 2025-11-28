from urllib.request import Request
from app.db.Connection import database
from app.services import metrics
from sqlalchemy.orm import Session
from app.db.Models.models import URLItem
from app.db import repository
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class URLService:

    @staticmethod
    def _validate_custom_alias(db: Session, custom_alias: Optional[str]):
        if not custom_alias:
            return None
        # Only check uniqueness here; schema/length validated by Pydantic DTO
        if repository.get_url_by_short_code(db, custom_alias):
            logger.warning("Custom alias collision detected: '%s'.", custom_alias)
            raise ValueError("Custom alias already in use.")
        return custom_alias

    @staticmethod
    def create_short_url(db: Session, original_url: str, custom_alias: Optional[str]) -> URLItem:
        # Validate custom alias if provided
        alias = URLService._validate_custom_alias(db, custom_alias)
        if alias:
            return repository.create_url(db, alias, original_url)

        # Idempotency: return existing mapping if present
        existing = repository.get_url_by_original(db, original_url)
        if existing:
            logger.info("Idempotent request: Returned existing short code '%s' for URL: %s", existing.short_code, original_url[:50])
            return existing

        # Let repository.create_url generate the short_code from DB id
        return repository.create_url(db, alias, original_url)

    @staticmethod
    def get_url_stats(db: Session, short_code: str):
        return repository.get_url_by_short_code(db, short_code)

    @staticmethod
    def get_url_by_short_code(db: Session, short_code: str):
        long_url = repository.get_url_by_short_code(db, short_code)
        URLService.add_to_cache(short_code, long_url)
        return long_url

    @staticmethod
    def check_in_cache(short_code: str, request: Request):
        cached_url = database.redis_client.get(f"url:{short_code}")
        if cached_url:
            try:
                cached_decoded = cached_url.decode() if isinstance(cached_url, (bytes, bytearray)) else str(cached_url)
            except Exception:
                cached_decoded = str(cached_url)

            logger.info(f"Redirect cache HIT for {short_code} -> {cached_decoded}")
            return cached_decoded
        
    @staticmethod
    def add_to_cache(short_code: str, db_url):
        # 4. Set Cache (TTL 24 hours = 86400 seconds)
        database.redis_client.setex(f"url:{short_code}", 86400, db_url.original_url)
        logger.info(f"Redirect cache MISS/DB HIT for {short_code} -> {db_url.original_url[:50]}...")