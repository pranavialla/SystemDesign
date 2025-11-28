from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import logging

from app.db.Models.models import URLItem
from app.utils.encoding import generate_code_from_id

logger = logging.getLogger(__name__)


def get_url_by_short_code(db: Session, short_code: str) -> Optional[URLItem]:
    return db.query(URLItem).filter(URLItem.short_code == short_code).first()


def get_url_by_original(db: Session, original_url: str) -> Optional[URLItem]:
    return db.query(URLItem).filter(URLItem.original_url == original_url).first()


def create_url(db: Session, short_code: Optional[str], original_url: str) -> URLItem:
    """Create a URLItem. If short_code provided, attempt direct insert and
    raise ValueError on uniqueness conflict. Returns the created URLItem.
    """
    # If caller provided a custom short_code, try direct insert and fail fast on conflict
    if short_code is not None:
        db_url = URLItem(short_code=short_code, original_url=original_url)
        db.add(db_url)
        try:
            db.commit()
            db.refresh(db_url)
            return db_url
        except IntegrityError as e:
            db.rollback()
            logger.warning("IntegrityError creating URLItem short_code=%s original=%s: %s", short_code, original_url, str(e))
            raise ValueError("Short code or original URL already exists")

    # Otherwise, insert a row without a short_code to obtain a unique numeric id,
    # then generate a short_code from that id and update the record.
    db_url = URLItem(short_code=None, original_url=original_url)
    db.add(db_url)
    try:
        db.commit()
        db.refresh(db_url)
    except IntegrityError as e:
        db.rollback()
        logger.warning("IntegrityError creating URLItem for original=%s: %s", original_url, str(e))
        # If original_url already exists, return the existing row
        existing = get_url_by_original(db, original_url)
        if existing:
            return existing
        raise ValueError("Failed to create URLItem")

    # Generate a compact short code from the numeric id
    MAX_LEN = 10
    generated = generate_code_from_id(db_url.id, max_len=MAX_LEN)
    base = generated[:MAX_LEN]

    def _attempt_set(code: str) -> Optional[URLItem]:
        db_url.short_code = code
        try:
            db.commit()
            db.refresh(db_url)
            return db_url
        except IntegrityError:
            db.rollback()
            return None

    # First attempt: truncated base
    res = _attempt_set(base)
    if res:
        return res

    # If truncated code collides (unlikely), try deterministic suffixes
    import hashlib as _hashlib
    suffix_source = _hashlib.sha256(str(db_url.id).encode()).hexdigest()
    # Try up to 5 suffix variations
    for i in range(5):
        suffix = suffix_source[i * 2:(i * 2) + 2]
        candidate = (base[: MAX_LEN - len(suffix)] + suffix)[:MAX_LEN]
        res = _attempt_set(candidate)
        if res:
            return res

    # If still failing, escalate — this is extremely unlikely
    logger.error("Failed to generate unique short_code for id %s after retries", db_url.id)
    raise ValueError("Failed to generate unique short code")


def increment_click(db: Session, short_code: str) -> int:
    updated = db.query(URLItem).filter(URLItem.short_code == short_code).update({
        URLItem.click_count: URLItem.click_count + 1,
        URLItem.last_accessed_at: datetime.utcnow()
    })
    db.commit()
    return updated
