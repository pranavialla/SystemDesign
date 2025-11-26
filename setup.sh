#!/bin/bash

echo "Creating project structure..."

# Create necessary directories
mkdir -p app/core
mkdir -p app/db
mkdir -p app/schemas
mkdir -p app/services

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
    BASE_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"

settings = Settings()
EOF

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

echo "Writing app/db/models.py..."
cat << 'EOF' > app/db/models.py
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class URLItem(Base):
    __tablename__ = "urls"

    short_code = Column(String(10), primary_key=True, index=True)
    original_url = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)
    click_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

# NEW: Dynamic Configuration Table
class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
EOF

echo "Writing app/schemas/url.py..."
cat << 'EOF' > app/schemas/url.py
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional

class URLBase(BaseModel):
    url: HttpUrl

class URLCreate(URLBase):
    pass

class URLInfo(URLBase):
    short_code: str
    short_url: str
    created_at: datetime
    last_accessed_at: datetime
    click_count: int

    class Config:
        from_attributes = True

# NEW: Schema for Config updates
class ConfigUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
EOF

echo "Writing app/db/database.py..."
cat << 'EOF' > app/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
EOF

echo "Writing app/services/shortener.py..."
cat << 'EOF' > app/services/shortener.py
import hashlib
import base64
from sqlalchemy.orm import Session
from app.db.models import URLItem
from datetime import datetime

class URLService:
    @staticmethod
    def generate_short_code(original_url: str) -> str:
        hash_object = hashlib.sha256(original_url.encode())
        full_hash = base64.urlsafe_b64encode(hash_object.digest()).decode()[:8]
        return full_hash

    @staticmethod
    def create_short_url(db: Session, original_url: str) -> URLItem:
        existing_url = db.query(URLItem).filter(URLItem.original_url == original_url).first()
        if existing_url:
            return existing_url

        short_code = URLService.generate_short_code(original_url)
        
        collision_check = db.query(URLItem).filter(URLItem.short_code == short_code).first()
        if collision_check and collision_check.original_url != original_url:
            short_code = URLService.generate_short_code(original_url + "nonce")

        db_url = URLItem(short_code=short_code, original_url=original_url)
        db.add(db_url)
        db.commit()
        db.refresh(db_url)
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

echo "Writing app/main.py..."
cat << 'EOF' > app/main.py
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
EOF

echo "Writing Dockerfile..."
cat << 'EOF' > Dockerfile
FROM python:3.11-alpine as builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN apk add --no-cache postgresql-dev gcc python3-dev musl-dev
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.11-alpine
WORKDIR /app
RUN apk add --no-cache libpq
COPY --from=builder /install /usr/local
COPY . .
RUN adduser -D appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

echo "Writing docker-compose.yml..."
cat << 'EOF' > docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_SERVER=db
      - POSTGRES_DB=shortener_db
      - REDIS_HOST=redis
      - BASE_URL=http://localhost:8000
    depends_on:
      - db
      - redis

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=shortener_db

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
EOF

echo "Writing k8s-deployment.yaml..."
cat << 'EOF' > k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: url-shortener
  labels:
    app: url-shortener
spec:
  replicas: 3
  selector:
    matchLabels:
      app: url-shortener
  template:
    metadata:
      labels:
        app: url-shortener
    spec:
      containers:
      - name: url-shortener
        image: your-docker-registry/url-shortener:latest
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: password
        - name: POSTGRES_SERVER
          value: "postgres-service"
        - name: POSTGRES_DB
          value: "shortener_db"
        - name: REDIS_HOST
          value: "redis-service"
        resources:
          requests:
            memory: "64Mi"
            cpu: "250m"
          limits:
            memory: "128Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /docs
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: url-shortener-service
spec:
  selector:
    app: url-shortener
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
EOF

echo "Writing k8s-infra.yaml..."
cat << 'EOF' > k8s-infra.yaml
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  ports:
  - port: 6379
  selector:
    app: redis
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
spec:
  ports:
  - port: 5432
  selector:
    app: postgres
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        env:
        - name: POSTGRES_USER
          valueFrom:
             secretKeyRef:
               name: db-secrets
               key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
             secretKeyRef:
               name: db-secrets
               key: password
        - name: POSTGRES_DB
          value: "shortener_db"
EOF

echo "Done! Run 'docker --version
docker compose version   # note: newer Docker uses "docker compose" (space)' to start."

