import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from redis.connection import ConnectionPool
import redis
from sqlalchemy import text

SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
logger = logging.getLogger(__name__)
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

def verify_redis_connection():
    try:
        redis_client.ping()
        logger.info("Redis connection verified")
        return True
    except redis.exceptions.ConnectionError as e:
        logger.warning(f"Redis connection failed: {e}. Service will run with degraded performance.")
        return False
    except Exception as e:
        logger.error(f"Unexpected Redis error: {e}")
        return False


def verify_database_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False