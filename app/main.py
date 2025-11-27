from app.db.Connection import database
from fastapi import FastAPI, Request, status, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse
import redis.exceptions
import logging

from app.core.config import settings
from app.db.Models import models  # ensure these import the same Base
from app.api.endpoints import shortener, admin
from app.core.logging_config import configure_logging # NEW IMPORT
from app.services.shortener import URLService
from app.services import metrics
from sqlalchemy.orm import Session

# Initialize logging before application starts
logger = configure_logging()
logger.info(f"--- Application '{settings.PROJECT_NAME}' starting up. ---")

# Default values if config is not set in Redis/DB
RATE_LIMIT_DEFAULT_LIMIT = 100
RATE_LIMIT_DEFAULT_WINDOW = 60 # seconds

# Initialize Database Tables
# This runs after the DB is guaranteed to be available by healthcheck.sh
models.Base.metadata.create_all(bind=database.engine)
logger.info("Database models initialized/checked.")


app = FastAPI(
    title=settings.PROJECT_NAME, 
    description="Production-ready URL Shortener Service"
)

# --- Middleware ---

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Implement basic rate limiting per IP with dynamic configuration from Redis."""
    # Skip rate limiting for health/readiness probes and admin endpoints
    if request.url.path in ["/health", "/ready", "/health/live", "/health/ready"]:
        return await call_next(request)
    if request.url.path.startswith("/admin") or request.url.path.startswith("/api/v1/admin"):
        return await call_next(request)
    
    # --- Dynamic Config Fetch ---
    limit = RATE_LIMIT_DEFAULT_LIMIT
    window = RATE_LIMIT_DEFAULT_WINDOW
    
    try:
        # Fetch config from Redis (fastest access)
        limit_str = database.redis_client.get("config:RATE_LIMIT_LIMIT")
        window_str = database.redis_client.get("config:RATE_LIMIT_WINDOW")
        
        limit = int(limit_str) if limit_str else RATE_LIMIT_DEFAULT_LIMIT
        window = int(window_str) if window_str else RATE_LIMIT_DEFAULT_WINDOW
    except (redis.exceptions.ConnectionError, ValueError):
        # Fallback to hardcoded defaults if Redis is down or config is invalid
        logger.warning(f"Failed to fetch/parse dynamic rate limit config. Using defaults: {limit} requests per {window} seconds.")
    # --- End Dynamic Config Fetch ---

    # Prefer X-Forwarded-For when behind a proxy/load-balancer
    xff = request.headers.get("x-forwarded-for")
    client_ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
    key = f"rate_limit:{client_ip}"
    
    try:
        # Check Redis connection before attempting operations
        database.redis_client.ping()
        current = database.redis_client.get(key)
    except redis.exceptions.ConnectionError:
        # Fail open if Redis is down 
        logger.warning("Redis connection failed. Rate limiting is currently being skipped (failing open).")
        return await call_next(request)

    if current and int(current) >= limit:
        logger.info(f"Rate limit hit for IP: {client_ip}. Limit: {limit}/{window}s.")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
            content={"detail": f"Too many requests. Limit is {limit} per {window} seconds."}
        )
    
    pipe = database.redis_client.pipeline()
    pipe.incr(key, 1)
    if not current:
        pipe.expire(key, window)
    pipe.execute()
    
    return await call_next(request)

# --- Routers ---

# All API endpoints (shorten, stats, admin) are under /api/v1
app.include_router(shortener.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def read_root():
    return {"message": "URL Shortener Service is operational. See /docs for API details."}


@app.get("/{short_code}", include_in_schema=False)
def root_redirect(short_code: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    """Redirect root short codes (e.g. GET /abc123) to original URL using cache + DB.
    This keeps redirect available at the root while API endpoints live under /api/v1.
    """
    # 1. Try cache
    cached = None
    try:
        cached = database.redis_client.get(f"url:{short_code}")
    except Exception:
        logger.debug("Redis unavailable for redirect cache check.")

    if cached:
        # Schedule background task to increment counters (Redis + DB) once
        try:
            if not getattr(request.state, "metrics_scheduled", False):
                background_tasks.add_task(metrics.record_click, short_code)
                request.state.metrics_scheduled = True
        except Exception:
            logger.debug("Failed to schedule background DB metric update for cache hit")

        return RedirectResponse(url=cached, status_code=status.HTTP_302_FOUND)

    # 2. DB lookup
    db_url = URLService.get_url_stats(db, short_code)
    if db_url is None or not getattr(db_url, "is_active", True):
        raise HTTPException(status_code=404, detail="URL not found")

    # 3. increment clicks asynchronously to keep redirect latency low
    try:
        background_tasks.add_task(metrics.record_click, short_code)
    except Exception:
        logger.debug("Failed to schedule background DB metric update for DB hit")

    # 4. cache and redirect
    try:
        database.redis_client.setex(f"url:{short_code}", 86400, db_url.original_url)
    except Exception:
        logger.debug("Failed to set redirect cache in Redis.")

    return RedirectResponse(url=db_url.original_url, status_code=status.HTTP_302_FOUND)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Graceful shutdown handlers
import signal, sys

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
