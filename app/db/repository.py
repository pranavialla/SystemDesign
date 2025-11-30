from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import logging
from app.utils.encoding import  generate_short_code, normalize_short_code

from app.db.Models.models import URLItem

logger = logging.getLogger(__name__)


def get_url_by_short_code(db: Session, short_code: str) -> Optional[URLItem]:
    normalized = normalize_short_code(short_code)
    return db.query(URLItem).filter(URLItem.short_code == normalized).first()

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
    normalized = normalize_short_code(short_code)
    db_url = URLItem(short_code=normalized, original_url=original_url)
    try:
        return _commit_and_refresh(db, db_url)
    except IntegrityError:
        raise ValueError("Custom alias already exists")

def _create_and_generate_code(db: Session, original_url: str) -> URLItem:
    max_retries = 5
    
    for attempt in range(max_retries):
        short_code = generate_short_code()
        db_url = URLItem(short_code=short_code, original_url=original_url)
        
        try:
            return _commit_and_refresh(db, db_url)
        except IntegrityError as e:
            db.rollback()
            error_msg = str(e.orig).lower() if hasattr(e, 'orig') else str(e).lower()
            
            if "short_code" in error_msg or "unique" in error_msg:
                existing = get_url_by_original(db, original_url)
                if existing:
                    return existing
                logger.info(f"Short code collision on attempt {attempt + 1}/{max_retries}")
            elif "original_url" in error_msg:
                existing = get_url_by_original(db, original_url)
                if existing:
                    return existing
                raise ValueError("Failed to create URLItem")
            else:
                raise ValueError("Failed to create URLItem")
    
    raise ValueError(f"Failed to generate unique short code after {max_retries} attempts")

def create_url(db: Session, short_code: Optional[str], original_url: str) -> URLItem:
    if short_code:
        return _create_with_custom_code(db, short_code, original_url)
    return _create_and_generate_code(db, original_url)

def increment_click(db: Session, short_code: str) -> int:
    normalized = normalize_short_code(short_code)
    updated = db.query(URLItem).filter(URLItem.short_code == normalized).update({
        URLItem.click_count: URLItem.click_count + 1,
        URLItem.last_accessed_at: datetime.utcnow()
    })
    db.commit()
    return updated