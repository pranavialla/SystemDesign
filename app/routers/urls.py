from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
from app.db import database, models
from app.schemas.url import URLCreate, URLInfo
from app.services.shortener import URLService
from app.core.config import settings
import redis

router = APIRouter(tags=["urls"])

# local redis client instance for this router
redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)

@router.post("/shorten", response_model=URLInfo)
def shorten_url(url_request: URLCreate, db: Session = Depends(database.get_db)):
    # can add maintenance checks here if you have a system config
    db_obj = URLService.create_short_url(db, str(url_request.url))
    return URLInfo(
        short_code=db_obj.short_code,
        short_url=f"{settings.BASE_URL}/{db_obj.short_code}",
        original_url=db_obj.original_url,
        created_at=db_obj.created_at,
        last_accessed_at=db_obj.last_accessed_at,
        click_count=db_obj.click_count or 0,
    )

@router.get("/{short_code}")
def redirect_to_url(short_code: str, db: Session = Depends(database.get_db)):
    # try cache
    cached = redis_client.get(f"url:{short_code}")
    if cached:
        return RedirectResponse(cached)

    db_url = URLService.get_url_stats(db, short_code)
    if db_url is None or not db_url.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")

    URLService.increment_click(db, db_url)

    # cache for a day
    try:
        redis_client.setex(f"url:{short_code}", 86400, db_url.original_url)
    except Exception:
        pass

    return RedirectResponse(url=db_url.original_url)

@router.get("/stats/{short_code}", response_model=URLInfo)
def get_url_statistics(short_code: str, db: Session = Depends(database.get_db)):
    db_url = URLService.get_url_stats(db, short_code)
    if db_url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")
    return URLInfo(
        short_code=db_url.short_code,
        short_url=f"{settings.BASE_URL}/{db_url.short_code}",
        original_url=db_url.original_url,
        created_at=db_url.created_at,
        last_accessed_at=db_url.last_accessed_at,
        click_count=db_url.click_count or 0,
    )