from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List
import redis
import time
from datetime import datetime, timedelta
import signal
import sys
import structlog

from app.core.config import settings
from app.db import models, database
from app.schemas import URLCreateRequest, URLInfoResponse, ConfigUpdateRequest
from app.services.shortener import URLService
from fastapi import BackgroundTasks

from app.core.logging_config import configure_logging

# create app and configure logging
configure_logging()
app = FastAPI(title=settings.PROJECT_NAME)

# create DB tables (dev only)
models.Base.metadata.create_all(bind=database.engine)

# include routers (assumes app/routers/*.py exist)
from app.routers import health, admin, urls

app.include_router(health.router)
app.include_router(admin.router)
app.include_router(urls.router)

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

