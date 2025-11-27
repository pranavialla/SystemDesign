import hashlib
import base64
from sqlalchemy.orm import Session
from app.db.Models.models import URLItem
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class URLService:
    # Short code should be no longer than 10 characters
    @staticmethod
    def generate_short_code(original_url: str, salt: Optional[str] = "") -> str:
        # Use SHA-256 for determinism (idempotent requirement)
        hash_object = hashlib.sha256((original_url + salt).encode())
        # Base64 URL-safe encoding of the first 6 bytes gives 8 characters (~48 bits)
        # 8 characters is < 10 character max
        full_hash = base64.urlsafe_b64encode(hash_object.digest()).decode()[:8]
        return full_hash

    @staticmethod
    def create_short_url(db: Session, original_url: str, custom_alias: Optional[str]) -> URLItem:
        # 1. Handle Custom Alias
        if custom_alias:
            if db.query(URLItem).filter(URLItem.short_code == custom_alias).first():
                logger.warning(f"Custom alias collision detected: '{custom_alias}'.")
                raise ValueError("Custom alias already in use.")
            if len(custom_alias) > 10:
                logger.error(f"Custom alias rejected: '{custom_alias}' exceeds max length of 10.")
                raise ValueError("Custom alias must be 10 characters or less.")
            short_code = custom_alias
            # Skip idempotency check for custom links

        else:
            # 2. Idempotency Check (The same original URL should always return the same short code)
            existing_url = db.query(URLItem).filter(URLItem.original_url == original_url).first()
            if existing_url:
                logger.info(f"Idempotent request: Returned existing short code '{existing_url.short_code}' for URL: {original_url[:50]}...")
                return existing_url

            # 3. Generate Short Code & Handle Collision
            short_code = URLService.generate_short_code(original_url)
            collision_check = db.query(URLItem).filter(URLItem.short_code == short_code).first()
            # If the code is taken by a DIFFERENT URL, generate a new one using a "salt"
            if collision_check and collision_check.original_url != original_url:
                logger.warning(f"Short code collision detected for generated code '{short_code}'. Retrying with salt.")
                # Use a timestamp as salt to ensure a unique hash is generated
                short_code = URLService.generate_short_code(original_url, salt=str(datetime.utcnow()))

        # 4. Save to DB
        db_url = URLItem(short_code=short_code, original_url=original_url)
        db.add(db_url)
        db.commit()
        db.refresh(db_url)
        logger.info(f"New short URL created: {db_url.short_code} -> {db_url.original_url[:50]}...")
        return db_url

    @staticmethod
    def get_url_stats(db: Session, short_code: str):
        return db.query(URLItem).filter(URLItem.short_code == short_code).first()

    @staticmethod
    def increment_click(db: Session, db_obj: URLItem):
        db_obj.click_count += 1
        db_obj.last_accessed_at = datetime.utcnow()
        db.commit()
