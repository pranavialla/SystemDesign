from app.db.Connection import database
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import redis.exceptions
import logging

from app.core.config import settings
from app.db.Models import models  # ensure these import the same Base
from app.api.endpoints import shortener, admin
from app.core.logging_config import configure_logging # NEW IMPORT

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

    client_ip = request.client.host
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

# Include the shortener router again at the root for the redirect endpoint (/{short_code}) only.
app.include_router(shortener.router) 

@app.get("/", include_in_schema=False)
def read_root():
    return {"message": "URL Shortener Service is operational. See /docs for API details."}
