from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.config import get_settings

router = APIRouter()

@router.get("/health")
async def health():
    settings = get_settings()
    return {"status": "ok", "app": "caoms-api", "tenant_mode": settings.tenant_mode, "time": datetime.now(timezone.utc).isoformat()}

@router.get("/ready")
async def ready():
    # Check Firestore + Redis
    checks = {}
    try:
        from app.infra.firestore.client import get_db
        db = get_db()
        # Simple operation
        list(db.collection("health").limit(1).stream())
        checks["firestore"] = "ok"
    except Exception as e:
        checks["firestore"] = f"degraded: {e}"
    try:
        from app.infra.cache.redis_client import get_redis
        r = get_redis()
        # async ping
        import asyncio
        try:
            await r.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"degraded: {e}"
    except Exception as e:
        checks["redis"] = f"degraded: {e}"
    ok = all(v=="ok" for v in checks.values())
    return {"status": "ready" if ok else "degraded", "checks": checks}
