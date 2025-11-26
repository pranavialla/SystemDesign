from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List
import redis
import time
from datetime import datetime

from app.core.config import settings
from app.db import models, database
from app.schemas.url import URLCreate, URLInfo, ConfigUpdate
from app.services.shortener import URLService

# Initialize Database Tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title=settings.PROJECT_NAME)

redis_client = redis.Redis(
    host=settings.REDIS_HOST, 
    port=settings.REDIS_PORT, 
    decode_responses=True
)

# Helper to check dynamic configs
def check_maintenance_mode(db: Session):
    mode = db.query(models.SystemConfig).filter(models.SystemConfig.key == "maintenance_mode").first()
    if mode and mode.value.lower() == "true":
        return True
    return False

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"
    current = redis_client.get(key)
    
    # We could even make the limit dynamic!
    limit = 100 # Default
    
    if current and int(current) > limit:
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    
    pipe = redis_client.pipeline()
    pipe.incr(key, 1)
    if not current:
        pipe.expire(key, 60)
    pipe.execute()
    
    return await call_next(request)

# --- Admin Config Endpoints ---

@app.post("/admin/config")
def set_dynamic_config(config: ConfigUpdate, db: Session = Depends(database.get_db)):
    """Set a dynamic configuration value (e.g. maintenance_mode=true)"""
    db_config = db.query(models.SystemConfig).filter(models.SystemConfig.key == config.key).first()
    if not db_config:
        db_config = models.SystemConfig(key=config.key, value=config.value, description=config.description)
        db.add(db_config)
    else:
        db_config.value = config.value
        db_config.updated_at = datetime.utcnow()
    
    db.commit()
    return {"message": f"Config '{config.key}' updated to '{config.value}'"}

@app.get("/admin/config")
def get_all_configs(db: Session = Depends(database.get_db)):
    return db.query(models.SystemConfig).all()

# --- Main App Endpoints ---

@app.post("/shorten", response_model=URLInfo)
def shorten_url(url_request: URLCreate, db: Session = Depends(database.get_db)):
    # Hybrid Approach: Check DB for business rule
    if check_maintenance_mode(db):
        raise HTTPException(status_code=503, detail="System is currently in maintenance mode.")

    db_url = URLService.create_short_url(db, str(url_request.url))
    
    return URLInfo(
        url=db_url.original_url,
        short_code=db_url.short_code,
        short_url=f"{settings.BASE_URL}/{db_url.short_code}",
        created_at=db_url.created_at,
        last_accessed_at=db_url.last_accessed_at,
        click_count=db_url.click_count
    )

@app.get("/{short_code}")
def redirect_to_url(short_code: str, db: Session = Depends(database.get_db)):
    # 1. Check Cache
    cached_url = redis_client.get(f"url:{short_code}")
    if cached_url:
        return RedirectResponse(url=cached_url)

    # 2. Check Database
    db_url = URLService.get_url_stats(db, short_code)
    if db_url is None:
        raise HTTPException(status_code=404, detail="URL not found")

    # 3. Update Stats
    URLService.increment_click(db, db_url)

    # 4. Set Cache
    redis_client.setex(f"url:{short_code}", 86400, db_url.original_url)

    return RedirectResponse(url=db_url.original_url)

@app.get("/stats/{short_code}", response_model=URLInfo)
def get_url_statistics(short_code: str, db: Session = Depends(database.get_db)):
    db_url = URLService.get_url_stats(db, short_code)
    if db_url is None:
        raise HTTPException(status_code=404, detail="URL not found")
        
    return URLInfo(
        url=db_url.original_url,
        short_code=db_url.short_code,
        short_url=f"{settings.BASE_URL}/{db_url.short_code}",
        created_at=db_url.created_at,
        last_accessed_at=db_url.last_accessed_at,
        click_count=db_url.click_count
    )

@app.get("/admin/list", response_model=List[URLInfo])
def list_urls(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    urls = db.query(models.URLItem).offset(skip).limit(limit).all()
    return [
        URLInfo(
            url=u.original_url,
            short_code=u.short_code,
            short_url=f"{settings.BASE_URL}/{u.short_code}",
            created_at=u.created_at,
            last_accessed_at=u.last_accessed_at,
            click_count=u.click_count
        ) for u in urls
    ]
