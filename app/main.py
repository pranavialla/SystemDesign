from app.db.Connection import database
from fastapi import FastAPI, Request, status, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse
import redis.exceptions
import logging
import signal, sys

from app.core.config import settings
from app.db.Models import models  
from app.api import shortener, admin
from app.core.logging_config import configure_logging 
from app.services.shortener import URLService
from app.services import metrics
from sqlalchemy.orm import Session
from app.RateLimitHelper import *

logger = configure_logging()
logger.info(f"Application '{settings.PROJECT_NAME}' starting up.")

models.Base.metadata.create_all(bind=database.engine)
logger.info("Database models initialized/checked.")


app = FastAPI(
    title=settings.PROJECT_NAME, 
    description="Production-ready URL Shortener Service"
)

app.include_router(shortener.router, prefix="")
app.include_router(admin.router, prefix="/api/v1")

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "healthy", "service": "url-shortener"}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not is_admin_path(request.url.path):
        return await call_next(request)

    limit, window = get_rate_limit_config(database)
    client_ip = get_client_ip(request)
    key = f"rate_limit:{client_ip}"

    allowed = check_rate_limit(database, key, limit, window)
    if allowed is False:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(window)},
            content={"detail": f"Too many requests. Limit is {limit} per {window} seconds."}
        )

    return await call_next(request)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

def _shutdown(signum, frame):
    logger.info("Shutting down gracefully...")
    try:
        database.engine.dispose()
    except Exception:
        logger.debug("Error disposing DB engine")
    try:
        database.redis_client.close()
    except Exception:
        logger.debug("Error closing Redis client")
    sys.exit(0)

signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)
