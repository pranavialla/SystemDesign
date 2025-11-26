#!/bin/bash

echo "Creating project structure and applying final logging and environment fixes..."

# Create necessary directories
mkdir -p app/core
mkdir -p app/db
mkdir -p app/schemas
mkdir -p app/services
mkdir -p app/api/endpoints
touch app/__init__.py app/db/__init__.py app/api/__init__.py app/api/endpoints/__init__.py

# --- Health Check Script (No Change) ---
echo "Writing healthcheck.sh..."
cat << 'EOF' > healthcheck.sh
#!/bin/sh
# Wait until PostgreSQL is ready to accept connections

set -e
host="$1"
shift
cmd="$@"

# Using hardcoded values matching docker-compose.yml for simplicity.
until PGPASSWORD="password" psql -h "$host" -U "user" -d "shortener_db" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing application command"
exec $cmd
EOF

# Make the healthcheck script executable immediately
chmod +x healthcheck.sh

# --- Core Config (No Change) ---
echo "Writing app/core/config.py..."
cat << 'EOF' > app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "URL Shortener"
    
    # Infrastructure Configs (Env Vars - Required to start app)
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str
    
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    BASE_URL: str = "http://localhost:8080" # CORRECTED PORT TO 8080

    class Config:
        env_file = ".env"

settings = Settings()
EOF

# --- NEW: Logging Configuration (No Change) ---
echo "Writing app/core/logging_config.py..."
cat << 'EOF' > app/core/logging_config.py
import logging
import sys

def configure_logging():
    """
    Configures application logging for production use.
    Logs to stdout with a structured, timestamped format.
    """
    # 1. Basic configuration for all loggers
    logging.basicConfig(
        level=logging.INFO,
        # Production-ready format: Timestamp | Level | Module Name | Function:Line | Message
        format='%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # 2. Configure Uvicorn/FastAPI loggers to use the same output format
    logging.getLogger("uvicorn.error").propagate = True
    # Disable default access logs; Uvicorn's default access logging can be verbose/redundant
    logging.getLogger("uvicorn.access").disabled = True 

    # 3. Suppress chattiness from libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)

    # Return the root app logger
    return logging.getLogger("app")
EOF

# --- Requirements (No Change) ---
echo "Writing requirements.txt..."
cat << 'EOF' > requirements.txt
fastapi==0.109.0
uvicorn==0.27.0
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
redis==5.0.1
pydantic==2.5.3
pydantic-settings==2.1.0
email-validator==2.1.0
EOF

# --- DB Models (No Change) ---
echo "Writing app/db/models.py..."
cat << 'EOF' > app/db/models.py
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class URLItem(Base):
    __tablename__ = "urls"

    # Short Code: Must be unique and max 10 chars
    short_code = Column(String(10), primary_key=True, index=True)
    original_url = Column(String, index=True, nullable=False)
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)
    click_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

# For dynamic configs / maintenance mode
class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
EOF

# --- Schemas (DTOs) (No Change) ---
echo "Writing app/schemas/url.py..."
cat << 'EOF' > app/schemas/url.py
from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, List

# Request DTOs
class URLCreateRequest(BaseModel):
    # original_url is the Python field, 'url' is the JSON key
    original_url: HttpUrl = Field(..., alias="url")
    custom_alias: Optional[str] = None # Bonus feature

# Response DTOs
class URLInfoResponse(BaseModel):
    # original_url is the Python field, 'url' is the JSON key
    original_url: HttpUrl = Field(..., alias="url")
    short_code: str
    short_url: str
    created_at: datetime
    last_accessed_at: datetime
    click_count: int

    class Config:
        from_attributes = True
        # CRITICAL FIX for Pydantic V2: Allows instantiation using the Python field name 'original_url'
        # even though it has an alias 'url'.
        populate_by_name = True 

class ConfigUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class PaginatedURLList(BaseModel):
    total: int
    skip: int
    limit: int
    urls: List[URLInfoResponse]
EOF

# --- DB Connection (No Change) ---
echo "Writing app/db/database.py..."
cat << 'EOF' > app/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import redis

SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency to get a SQLAlchemy DB Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

redis_client = redis.Redis(
    host=settings.REDIS_HOST, 
    port=settings.REDIS_PORT, 
    decode_responses=True
)
EOF

# --- Core Service Logic (No Change) ---
echo "Writing app/services/shortener.py..."
cat << 'EOF' > app/services/shortener.py
import hashlib
import base64
from sqlalchemy.orm import Session
from app.db.models import URLItem
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class URLService:
    # Short code should be no longer than 10 characters
    @staticmethod
    def generate_short_code(original_url: str, salt: Optional[str] = "") -> str:
        # Use SHA-256 for determinism (idempotent requirement)
        hash_object = hashlib.sha256((original_url + salt).encode())
        # Base64 URL-safe encoding of the first 6 bytes gives 8 characters (~48 bits)
        # 8 characters is < 10 character max
        full_hash = base64.urlsafe_b64encode(hash_object.digest()).decode()[:8]
        return full_hash

    @staticmethod
    def create_short_url(db: Session, original_url: str, custom_alias: Optional[str]) -> URLItem:
        # 1. Handle Custom Alias
        if custom_alias:
            if db.query(URLItem).filter(URLItem.short_code == custom_alias).first():
                logger.warning(f"Custom alias collision detected: '{custom_alias}'.")
                raise ValueError("Custom alias already in use.")
            if len(custom_alias) > 10:
                logger.error(f"Custom alias rejected: '{custom_alias}' exceeds max length of 10.")
                raise ValueError("Custom alias must be 10 characters or less.")
            short_code = custom_alias
            # Skip idempotency check for custom links

        else:
            # 2. Idempotency Check (The same original URL should always return the same short code)
            existing_url = db.query(URLItem).filter(URLItem.original_url == original_url).first()
            if existing_url:
                logger.info(f"Idempotent request: Returned existing short code '{existing_url.short_code}' for URL: {original_url[:50]}...")
                return existing_url

            # 3. Generate Short Code & Handle Collision
            short_code = URLService.generate_short_code(original_url)
            collision_check = db.query(URLItem).filter(URLItem.short_code == short_code).first()
            # If the code is taken by a DIFFERENT URL, generate a new one using a "salt"
            if collision_check and collision_check.original_url != original_url:
                logger.warning(f"Short code collision detected for generated code '{short_code}'. Retrying with salt.")
                # Use a timestamp as salt to ensure a unique hash is generated
                short_code = URLService.generate_short_code(original_url, salt=str(datetime.utcnow()))

        # 4. Save to DB
        db_url = URLItem(short_code=short_code, original_url=original_url)
        db.add(db_url)
        db.commit()
        db.refresh(db_url)
        logger.info(f"New short URL created: {db_url.short_code} -> {db_url.original_url[:50]}...")
        return db_url

    @staticmethod
    def get_url_stats(db: Session, short_code: str):
        return db.query(URLItem).filter(URLItem.short_code == short_code).first()

    @staticmethod
    def increment_click(db: Session, db_obj: URLItem):
        db_obj.click_count += 1
        db_obj.last_accessed_at = datetime.utcnow()
        db.commit()
EOF

# --- API Endpoints (Shortener Router) (FIXED Logging) ---
echo "Writing app/api/endpoints/shortener.py..."
cat << 'EOF' > app/api/endpoints/shortener.py
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

# Helper to check dynamic configs
def check_maintenance_mode(db: Session):
    from app.db.models import SystemConfig # Import locally to avoid circular dependency
    mode = database.redis_client.get("config:maintenance_mode")
    # Check redis first, fallback to DB if not in cache (less common config)
    if mode:
        return mode.decode().lower() == "true"
        
    db_mode = db.query(SystemConfig).filter(SystemConfig.key == "maintenance_mode").first()
    if db_mode and db_mode.value.lower() == "true":
        return True
    return False

@router.post("/shorten", response_model=URLInfoResponse, status_code=status.HTTP_201_CREATED)
def shorten_url_endpoint(url_request: URLCreateRequest, db: Session = Depends(database.get_db)):
    """
    Submit a long URL and receive a shortened version.
    """
    if check_maintenance_mode(db):
        logger.warning("Attempted shorten request during maintenance mode.")
        raise HTTPException(status_code=503, detail="System is currently in maintenance mode.")

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
EOF

# --- API Endpoints (Admin Router) (No Change) ---
echo "Writing app/api/endpoints/admin.py..."
cat << 'EOF' > app/api/endpoints/admin.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List
import logging

from app.db import database, models
from app.schemas.url import URLInfoResponse, ConfigUpdate, PaginatedURLList
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
EOF

# --- Main App Entry (No Change) ---
echo "Writing app/main.py..."
cat << 'EOF' > app/main.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import redis.exceptions
import logging

from app.core.config import settings
from app.db import models, database
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
EOF

# --- Dockerfile (No Change - still 8080) ---
echo "Writing Dockerfile..."
cat << 'EOF' > Dockerfile
# Stage 1: Builder
FROM python:3.11-alpine as builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Install build dependencies for psycopg2
RUN apk add --no-cache postgresql-dev gcc python3-dev musl-dev
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Final lightweight image
FROM python:3.11-alpine
WORKDIR /app
# Install runtime dependencies
RUN apk add --no-cache libpq
# Install PostgreSQL client tools (required for healthcheck.sh)
RUN apk add --no-cache postgresql-client 

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local
# Copy application code and health check script
COPY . .
# Create and switch to a non-root user for security
RUN adduser -D appuser
USER appuser
# Expose the service on port 8080
EXPOSE 8080
# NOTE: CMD is set by docker-compose to run the healthcheck wrapper first
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
EOF

# --- Docker Compose (No Change - still 8080) ---
echo "Writing docker-compose.yml..."
cat << 'EOF' > docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      # Map container port 8080 to host port 8080
      - "8080:8080"
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_SERVER: db 
      POSTGRES_DB: shortener_db
      REDIS_HOST: redis 
      BASE_URL: http://localhost:8080
    
    # Ensures the application waits for the DB before running uvicorn
    command: /app/healthcheck.sh db uvicorn app.main:app --host 0.0.0.0 --port 8080
    
    depends_on:
      - db
      - redis
    stop_signal: SIGINT

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: shortener_db

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
EOF

# --- Environment File Placeholder (No Change) ---
echo "Writing .env placeholder..."
cat << 'EOF' > .env
# --- Application Configuration ---
BASE_URL=http://localhost:8080

# --- PostgreSQL Configuration (Must match docker-compose.yml) ---
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_SERVER=db
POSTGRES_PORT=5432
POSTGRES_DB=shortener_db

# --- Redis Configuration (Must match docker-compose.yml) ---
REDIS_HOST=redis
REDIS_PORT=6379
EOF

echo "All files have been written with debugging fixes applied."