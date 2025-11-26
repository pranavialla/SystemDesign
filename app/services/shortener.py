import hashlib
import base64
import time
import random
import string
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db import models


class URLService:
    @staticmethod
    def generate_short_code(original_url: str, length: int = 8) -> str:
        """
        Deterministic-ish short code: sha256 -> urlsafe base64 -> prefix.
        """
        h = hashlib.sha256(original_url.encode("utf-8")).digest()
        code = base64.urlsafe_b64encode(h).decode("utf-8").rstrip("=")
        # keep alnum and replace any problematic chars
        code = "".join(ch if ch.isalnum() else "0" for ch in code)
        return code[:length]

    @staticmethod
    def create_short_url(db: Session, original_url: str) -> models.URLItem:
        """
        Return existing record for original_url or create a new unique short code.
        Handles collisions by re-hashing with a nonce (limited attempts).
        """
        # return existing if already shortened
        existing = db.query(models.URLItem).filter(models.URLItem.original_url == original_url).first()
        if existing:
            return existing

        # generate code and handle collisions
        attempt = 0
        max_attempts = 6
        code = URLService.generate_short_code(original_url)
        collision = db.query(models.URLItem).filter(models.URLItem.short_code == code).first()
        while collision and attempt < max_attempts:
            nonce = f"{time.time()}-{random.choice(string.ascii_letters)}"
            code = URLService.generate_short_code(original_url + nonce)
            collision = db.query(models.URLItem).filter(models.URLItem.short_code == code).first()
            attempt += 1

        if collision:
            # fallback to random code
            code = "".join(random.choices(string.ascii_letters + string.digits, k=8))

        now = datetime.utcnow()
        new_item = models.URLItem(
            short_code=code,
            original_url=original_url,
            created_at=now,
            last_accessed_at=None,
            click_count=0,
            is_active=True,
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item

    @staticmethod
    def get_url_stats(db: Session, short_code: str) -> Optional[models.URLItem]:
        return db.query(models.URLItem).filter(models.URLItem.short_code == short_code).first()

    @staticmethod
    def increment_click(db: Session, db_obj: models.URLItem) -> None:
        db_obj.click_count = (db_obj.click_count or 0) + 1
        db_obj.last_accessed_at = datetime.utcnow()
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

