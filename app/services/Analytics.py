from app.db.Connection import database
from app.db.Models import models
from app.schemas.URLInfoResponse import URLInfoResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.config import settings

class URL:
    def get_all(skip : int, limit: int,  db: Session):
        total = db.query(func.count(models.URLItem.short_code)).scalar()
        urls = db.query(models.URLItem).offset(skip).limit(limit).all()
        url_responses = [
            URLInfoResponse(
                original_url=u.original_url,
                short_code=u.short_code,
                short_url=f"{settings.BASE_URL}/{u.short_code}",
                created_at=u.created_at,
                last_accessed_at=u.last_accessed_at,
                click_count=u.click_count
            ) for u in urls
        ]
        return total, url_responses
    