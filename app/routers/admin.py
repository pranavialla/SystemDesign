from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import models, database
from app.core.config import settings
import redis

router = APIRouter(prefix="/admin", tags=["admin"])

def get_redis_client():
    return redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)

@router.get("/metrics")
def admin_metrics(db: Session = Depends(database.get_db)):
    # Basic DB metrics
    total_urls = db.query(models.URLItem).count()
    active_urls = db.query(models.URLItem).filter(models.URLItem.is_active == True).count()

    # Basic Redis info (safe/catch errors)
    r = get_redis_client()
    redis_info = {}
    try:
        info = r.info()
        redis_info["used_memory_human"] = info.get("used_memory_human")
        redis_info["connected_clients"] = info.get("connected_clients")
        redis_info["keyspace_hits"] = info.get("keyspace_hits")
        redis_info["keyspace_misses"] = info.get("keyspace_misses")
    except Exception as e:
        redis_info["error"] = str(e)

    return {
        "db": {"total_urls": total_urls, "active_urls": active_urls},
        "redis": redis_info,
    }