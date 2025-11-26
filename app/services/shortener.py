import hashlib
import base64
from sqlalchemy.orm import Session
from app.db.models import URLItem
from datetime import datetime

class URLService:
    @staticmethod
    def generate_short_code(original_url: str) -> str:
        hash_object = hashlib.sha256(original_url.encode())
        full_hash = base64.urlsafe_b64encode(hash_object.digest()).decode()[:8]
        return full_hash

    @staticmethod
    def create_short_url(db: Session, original_url: str) -> URLItem:
        existing_url = db.query(URLItem).filter(URLItem.original_url == original_url).first()
        if existing_url:
            return existing_url

        short_code = URLService.generate_short_code(original_url)
        
        collision_check = db.query(URLItem).filter(URLItem.short_code == short_code).first()
        if collision_check and collision_check.original_url != original_url:
            short_code = URLService.generate_short_code(original_url + "nonce")

        db_url = URLItem(short_code=short_code, original_url=original_url)
        db.add(db_url)
        db.commit()
        db.refresh(db_url)
        return db_url

    @staticmethod
    def get_url_stats(db: Session, short_code: str):
        return db.query(URLItem).filter(URLItem.short_code == short_code).first()

    @staticmethod
    def increment_click(db: Session, db_obj: URLItem):
        db_obj.click_count += 1
        db_obj.last_accessed_at = datetime.utcnow()
        db.commit()
