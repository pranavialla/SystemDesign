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
