from urllib.request import Request
from app.db.Connection import database
from app.services import metrics
from sqlalchemy.orm import Session
from app.db.Models.models import URLItem
from app.db import repository
from typing import Optional
import logging
from app.services import RedisURLCache


logger = logging.getLogger(__name__)


class URLService:

    @staticmethod
    def validate_custom_alias(db: Session, custom_alias: Optional[str]):
        if not custom_alias:
            return None
        # Only check uniqueness here; schema/length validated by Pydantic DTO
        if repository.get_url_by_short_code(db, custom_alias):
            logger.warning("Custom alias collision detected: '%s'.", custom_alias)
            raise ValueError("Custom alias already exists")
        return custom_alias

    @staticmethod
    def create_short_url(db: Session, original_url: str, custom_alias: Optional[str]) -> URLItem:
        # Validate custom alias if provided
        alias = URLService.validate_custom_alias(db, custom_alias)
        if alias:
            url_item = repository.create_url(db, alias, original_url)
            RedisURLCache.put(alias, url_item)
            return url_item

        # Idempotency: return existing mapping if present
        existing = repository.get_url_by_original(db, original_url)
        if existing:
            logger.info("short URL already existed : '%s' for URL: %s", existing.short_code, original_url[:50])
            return existing

        # Let repository.create_url generate the short_code from DB id
        url_item = repository.create_url(db, alias, original_url)
        RedisURLCache.put(url_item.short_code, url_item)
        return url_item

    @staticmethod
    def get_url_stats(db: Session, short_code: str):
        return repository.get_url_by_short_code(db, short_code)

    @staticmethod
    def get_url_by_short_code(db: Session, short_code: str):
        long_url = repository.get_url_by_short_code(db, short_code)
        if long_url:
            RedisURLCache.put(short_code, long_url)
            return long_url