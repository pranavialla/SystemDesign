from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from redis.connection import ConnectionPool
import redis

SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

# Create SQLAlchemy engine with pool_pre_ping for resilience
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db():
    """Dependency to get a SQLAlchemy DB Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Configure Redis connection pool with sensible defaults
pool = ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True,
    max_connections=50,
    socket_connect_timeout=2,
    socket_keepalive=True,
    retry_on_timeout=True,
)

redis_client = redis.Redis(connection_pool=pool)
