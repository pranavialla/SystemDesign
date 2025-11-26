from fastapi import APIRouter
from app.core.config import settings
from app.db import database
import redis

router = APIRouter(tags=["health"])

# simple liveness
@router.get("/health")
def health():
    return {"status": "ok"}

# readiness: check DB + Redis connectivity
@router.get("/ready")
def readiness():
    details = {"db": "unknown", "redis": "unknown"}
    # check postgres
    try:
        with database.engine.connect() as conn:
            conn.execute("SELECT 1")
        details["db"] = "ok"
    except Exception as e:
        details["db"] = f"error: {str(e)}"

    # check redis
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, socket_connect_timeout=1)
        r.ping()
        details["redis"] = "ok"
    except Exception as e:
        details["redis"] = f"error: {str(e)}"

    ready = details["db"] == "ok" and details["redis"] == "ok"
    return {"ready": ready, "details": details}