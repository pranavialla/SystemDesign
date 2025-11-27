from app.db.Connection import database
from app.services.shortener import URLService
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List
import logging

from app.db.Models import models
from app.schemas.URLInfoResponse import URLInfoResponse
from app.schemas.ConfigUpdate import ConfigUpdate
from app.schemas.PaginatedURLList import PaginatedURLList
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/config", response_model=ConfigUpdate)
def set_dynamic_config_endpoint(config: ConfigUpdate, db: Session = Depends(database.get_db)):
    """Set a dynamic configuration value. Also saves to Redis for quick access by middleware."""
    # 1. Save to PostgreSQL for persistence and listing
    db_config = db.query(models.SystemConfig).filter(models.SystemConfig.key == config.key).first()
    if not db_config:
        db_config = models.SystemConfig(key=config.key, value=config.value, description=config.description)
        db.add(db_config)
    else:
        db_config.value = config.value
        db_config.description = config.description
        db_config.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_config)

    # 2. Save to Redis for fast access by middleware (e.g., rate limiting)
    database.redis_client.set(f"config:{config.key}", config.value)
    
    logger.info(f"Admin config updated: {config.key} = {config.value}")
    return config

@router.get("/config")
def get_all_configs_endpoint(db: Session = Depends(database.get_db)):
    logger.info("Admin accessed all system configurations.")
    return db.query(models.SystemConfig).all()

# --- URL Listing Endpoints ---

@router.get("/list", response_model=PaginatedURLList)
def list_urls_endpoint(
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, ge=1, le=1000), 
    db: Session = Depends(database.get_db)
):
    """
    Paginated listing of all shortened URLs (for admin use).
    """
    logger.info(f"Admin accessed URL list: skip={skip}, limit={limit}")
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

    return PaginatedURLList(
        total=total,
        skip=skip,
        limit=limit,
        urls=url_responses
    )

# --- Analytics Endpoint (Bonus) ---

@router.get("/analytics/total_clicks", response_model=dict)
def get_total_clicks(db: Session = Depends(database.get_db)):
    """Total clicks across all URLs. (Bonus Feature)"""
    logger.info("Admin accessed total click analytics.")
    total_clicks = db.query(func.sum(models.URLItem.click_count)).scalar()
    return {"total_clicks": total_clicks if total_clicks else 0}


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