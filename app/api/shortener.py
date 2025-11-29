from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.core.config import settings
from app.db.Connection import database
from app.schemas.URLInfoResponse import URLInfoResponse
from app.schemas.URLCreateRequest import URLCreateRequest 
from app.services.shortener import URLService
from app.services import RedisURLCache, metrics
from app.db.Models import models

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/v1/shorten", response_model=URLInfoResponse, status_code=status.HTTP_201_CREATED)
def shorten_url_endpoint(url_request: URLCreateRequest, db: Session = Depends(database.get_db)):
    try:
        db_url = URLService.create_short_url(db, str(url_request.original_url),url_request.custom_alias)
    except ValueError as e:
        original_url_str = str(url_request.original_url)
        logger.error(
            f"Failed to create short URL for {original_url_str[:50]}.. due to: {str(e)}"
        )
        raise HTTPException(status_code=409, detail=str(e)) 

    logger.info(
        f"API success: Shortened {db_url.original_url[:50]}... to {db_url.short_code}"
    )
    return URLInfoResponse(
        original_url=db_url.original_url,
        short_code=db_url.short_code,
        short_url=f"{settings.BASE_URL}/{db_url.short_code}",
        created_at=db_url.created_at,
        last_accessed_at=db_url.last_accessed_at,
        click_count=db_url.click_count,
    )

@router.get("/{short_code}", tags=["redirect"])
def redirect_to_url_endpoint(short_code: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    cached_url = RedisURLCache.get(short_code, request)
    if cached_url:
        metrics.update_stat(request ,background_tasks, short_code)
        return RedirectResponse(url=cached_url, status_code=status.HTTP_302_FOUND)
   
    db_url = URLService.get_url_by_short_code(db, short_code)
    if db_url is None:
        logger.warning(f"Redirect 404: Short code not found: {short_code}")
        raise HTTPException(status_code=404, detail="URL not found")

    metrics.update_stat(request ,background_tasks, short_code)
    return RedirectResponse(url=db_url.original_url, status_code=status.HTTP_302_FOUND)


