from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.core.config import settings
from app.db import database
from app.schemas.url import URLCreateRequest, URLInfoResponse
from app.services.shortener import URLService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/shorten", response_model=URLInfoResponse, status_code=status.HTTP_201_CREATED)
def shorten_url_endpoint(url_request: URLCreateRequest, db: Session = Depends(database.get_db)):
    """
    Submit a long URL and receive a shortened version.
    """
    try:
        # url_request.original_url is a Pydantic HttpUrl object
        db_url = URLService.create_short_url(
            db, 
            # Convert to string before passing to service
            str(url_request.original_url), 
            url_request.custom_alias
        )
    except ValueError as e:
        # FIX: Convert url_request.original_url to string before slicing for logging.
        original_url_str = str(url_request.original_url)
        logger.error(f"Failed to create short URL for {original_url_str[:50]}... due to: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    logger.info(f"API success: Shortened {db_url.original_url[:50]}... to {db_url.short_code}")
    return URLInfoResponse(
        original_url=db_url.original_url,
        short_code=db_url.short_code,
        short_url=f"{settings.BASE_URL}/{db_url.short_code}", # e.g., https://sho.rt/abc123
        created_at=db_url.created_at,
        last_accessed_at=db_url.last_accessed_at,
        click_count=db_url.click_count
    )

@router.get("/{short_code}", tags=["redirect"])
def redirect_to_url_endpoint(short_code: str, db: Session = Depends(database.get_db)):
    """
    Access the shortened URL and get redirected to the original long URL.
    """
    # 1. Check Cache
    cached_url = database.redis_client.get(f"url:{short_code}")
    if cached_url:
        logger.info(f"Redirect cache HIT for {short_code} -> {cached_url}")
        return RedirectResponse(url=cached_url, status_code=status.HTTP_302_FOUND)

    # 2. Check Database
    db_url = URLService.get_url_stats(db, short_code)
    if db_url is None:
        logger.warning(f"Redirect 404: Short code not found: {short_code}")
        raise HTTPException(status_code=404, detail="URL not found")

    # 3. Update Stats
    URLService.increment_click(db, db_url)

    # 4. Set Cache (TTL 24 hours = 86400 seconds)
    database.redis_client.setex(f"url:{short_code}", 86400, db_url.original_url)
    logger.info(f"Redirect cache MISS/DB HIT for {short_code} -> {db_url.original_url[:50]}...")

    return RedirectResponse(url=db_url.original_url, status_code=status.HTTP_302_FOUND)

@router.get("/stats/{short_code}", response_model=URLInfoResponse)
def get_url_statistics_endpoint(short_code: str, db: Session = Depends(database.get_db)):
    """Retrieve metadata for a short code."""
    db_url = URLService.get_url_stats(db, short_code)
    if db_url is None:
        logger.warning(f"Stats 404: Short code not found: {short_code}")
        raise HTTPException(status_code=404, detail="URL not found")
        
    return URLInfoResponse(
        original_url=db_url.original_url,
        short_code=db_url.short_code,
        short_url=f"{settings.BASE_URL}/{db_url.short_code}",
        created_at=db_url.created_at,
        last_accessed_at=db_url.last_accessed_at,
        click_count=db_url.click_count
    )
