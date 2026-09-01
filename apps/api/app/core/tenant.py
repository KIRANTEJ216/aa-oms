from contextvars import ContextVar
from fastapi import Request, HTTPException
from app.core.config import get_settings

# ContextVar holds the resolved tenant_id for the current request
tenant_ctx: ContextVar[str] = ContextVar("tenant_id", default="")

# Single-tenant seed id — stable across restarts (derived from slug)
SEED_TENANT_ID = "aarav-advisors"  # slug used as logical id in single mode; Firestore doc id

def get_current_tenant() -> str:
    tid = tenant_ctx.get()
    if not tid:
        # In single mode, fallback to seed
        s = get_settings()
        if s.tenant_mode == "single":
            return s.seed_tenant_slug
        raise HTTPException(status_code=401, detail="Tenant not resolved")
    return tid

async def tenant_middleware(request: Request, call_next):
    s = get_settings()
    # Let CORS preflight through — browsers send OPTIONS without tenant headers
    if request.method == "OPTIONS":
        return await call_next(request)
    # Allow health/docs without tenant
    if request.url.path in ("/health", "/ready", "/docs", "/openapi.json", "/redoc", "/metrics"):
        return await call_next(request)

    # Resolve tenant
    # Priority: JWT claim > X-Tenant-ID header > subdomain (future)
    # In single mode: always seed tenant
    if s.tenant_mode == "single":
        resolved = s.seed_tenant_slug
    else:
        # Multi mode: require header or JWT
        header_tid = request.headers.get("X-Tenant-ID")
        # JWT will be validated by auth dependency; we peek if present
        auth = request.headers.get("Authorization", "")
        jwt_tid = None
        if auth.startswith("Bearer "):
            try:
                from app.core.security import decode_token
                payload = decode_token(auth.removeprefix("Bearer ").strip())
                jwt_tid = payload.get("tenant_id")
            except Exception:
                pass
        if jwt_tid and header_tid and jwt_tid != header_tid:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "X-Tenant-ID does not match JWT tenant_id"})
        resolved = jwt_tid or header_tid
        if not resolved:
            # Allow unauthenticated routes (login/register) to proceed without tenant
            if request.url.path.startswith("/api/v1/auth/"):
                resolved = s.seed_tenant_slug
            else:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=401, content={"detail": "Tenant not resolved. Provide X-Tenant-ID header."})

    token = tenant_ctx.set(resolved)
    try:
        response = await call_next(request)
        # Echo tenant for debugging (remove in prod if needed)
        response.headers["X-Resolved-Tenant"] = resolved
        return response
    finally:
        tenant_ctx.reset(token)
