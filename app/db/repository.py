from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import logging

from app.db.Models.models import URLItem
from app.utils.encoding import encode_base62

logger = logging.getLogger(__name__)


def get_url_by_short_code(db: Session, short_code: str) -> Optional[URLItem]:
    return db.query(URLItem).filter(URLItem.short_code == short_code).first()


def get_url_by_original(db: Session, original_url: str) -> Optional[URLItem]:
    return db.query(URLItem).filter(URLItem.original_url == original_url).first()


def _commit_and_refresh(db: Session, db_url: URLItem) -> URLItem:
    try:
        db.add(db_url)
        db.commit()
        db.refresh(db_url)
        return db_url
    except IntegrityError as e:
        db.rollback()
        logger.warning(
            "IntegrityError creating URLItem short_code=%s original=%s: %s",
            db_url.short_code, db_url.original_url, str(e)
        )
        raise

def _create_with_custom_code(db: Session, short_code: str, original_url: str) -> URLItem:
    db_url = URLItem(short_code=short_code, original_url=original_url)
    try:
        return _commit_and_refresh(db, db_url)
    except IntegrityError:
        raise ValueError("URL already exists")

def _create_and_generate_code(db: Session, original_url: str) -> URLItem:
    db_url = URLItem(short_code=None, original_url=original_url)
    try:
        _commit_and_refresh(db, db_url)
    except IntegrityError as e:
        existing = get_url_by_original(db, original_url)
        if existing:
            return existing
        raise ValueError("Failed to create URLItem")

    db_url.short_code = encode_base62(db_url.id)
    return _commit_and_refresh(db, db_url)

def create_url(db: Session, short_code: Optional[str], original_url: str) -> URLItem:
    if short_code:
        return _create_with_custom_code(db, short_code, original_url)
    return _create_and_generate_code(db, original_url)

def increment_click(db: Session, short_code: str) -> int:
    updated = db.query(URLItem).filter(URLItem.short_code == short_code).update({
        URLItem.click_count: URLItem.click_count + 1,
        URLItem.last_accessed_at: datetime.utcnow()
    })
    db.commit()
    return updated
