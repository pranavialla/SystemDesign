from app.db.Connection import database
from app.services.shortener import URLService
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import logging

from app.db.Models import models
from app.schemas.URLInfoResponse import URLInfoResponse
from app.schemas.ConfigUpdate import ConfigUpdate
from app.schemas.PaginatedURLList import PaginatedURLList
from app.core.config import settings
from app.services.configService import ConfigService
from app.services.Analytics import URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/list", response_model=PaginatedURLList)
def list_urls_endpoint(
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(database.get_db)
):
    total, url_responses = URL.get_all(skip, limit, db)
    return PaginatedURLList(
        total=total,
        skip=skip,
        limit=limit,
        urls=url_responses
    )

@router.get("/analytics/total_clicks", response_model=dict)
def get_total_clicks(db: Session = Depends(database.get_db)):
    total_clicks = db.query(func.sum(models.URLItem.click_count)).scalar()
    return {"total_clicks": total_clicks if total_clicks else 0}

@router.get("/stats/{short_code}", response_model=URLInfoResponse)
def get_url_statistics_endpoint(short_code: str, db: Session = Depends(database.get_db)):
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


@router.post("/config", response_model=ConfigUpdate)
def set_dynamic_config_endpoint(config: ConfigUpdate, db: Session = Depends(database.get_db)):
    ConfigService.save_to_db(config, db) 
    ConfigService.save_to_redis(config, db)
    logger.info(f"Admin config updated: {config.key} = {config.value}")
    return config

@router.get("/config")
def get_all_configs_endpoint(db: Session = Depends(database.get_db)):
    return db.query(models.SystemConfig).all()
