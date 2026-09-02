"""
Rate Limiting Module using slowapi with Redis backend.
Supports per-IP, per-user, per-tenant, and per-API-key limiting.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
from app.core.config import get_settings
from app.core.tenant import get_current_tenant
from app.infra.cache.redis_client import get_redis

settings = get_settings()

# ============================================================
# Key Functions for Different Limit Scopes
# ============================================================

def get_ip_key(request: Request) -> str:
    """Default: limit by client IP address."""
    return f"ip:{get_remote_address(request)}"

def get_user_key(request: Request) -> str:
    """Limit by authenticated user ID (falls back to IP)."""
    try:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            from app.core.security import decode_token
            payload = decode_token(auth.removeprefix("Bearer ").strip())
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
    except Exception:
        pass
    return get_ip_key(request)

def get_tenant_key(request: Request) -> str:
    """Limit by tenant (falls back to IP)."""
    try:
        tenant_id = get_current_tenant()
        if tenant_id:
            return f"tenant:{tenant_id}"
    except Exception:
        pass
    return get_ip_key(request)

def get_api_key(request: Request) -> str:
    """Limit by API key (falls back to IP)."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key[:12]}"
    return get_ip_key(request)

def get_combined_key(request: Request) -> str:
    """Combined key: most specific available (API key > user > tenant > IP)."""
    # Try API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key[:12]}"
    
    # Try authenticated user
    try:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            from app.core.security import decode_token
            payload = decode_token(auth.removeprefix("Bearer ").strip())
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
    except Exception:
        pass
    
    # Try tenant
    try:
        tenant_id = get_current_tenant()
        if tenant_id:
            return f"tenant:{tenant_id}"
    except Exception:
        pass
    
    # Fallback to IP
    return get_ip_key(request)

# ============================================================
# Rate Limit Configuration
# ============================================================

RATE_LIMITS = {
    # Auth endpoints - strict
    "auth_login": "5/minute",
    "auth_register": "3/minute",
    "auth_firebase": "10/minute",
    "auth_forgot": "2/minute",
    "auth_refresh": "10/minute",
    "auth_mfa": "10/minute",
    
    # API defaults
    "api_default": "100/minute",
    "api_read": "200/minute",
    "api_write": "30/minute",
    "api_delete": "10/minute",
    
    # Specific modules
    "support_chatbot": "20/minute",
    "support_create": "10/minute",
    "upload": "10/minute",
    "export": "5/minute",
    
    # Webhooks (higher limits for legitimate traffic)
    "webhook_n8n": "100/minute",
    "webhook_generic": "50/minute",
}

# Per-role multipliers (applied on top of base limits)
ROLE_MULTIPLIERS = {
    "Super Admin": 10.0,
    "Firm Admin": 5.0,
    "Partner": 5.0,
    "Manager": 2.0,
    "Article Assistant": 1.0,
    "Paid Assistant": 1.0,
    "Client": 0.5,
}

# ============================================================
# Limiter Instance
# ============================================================

# Use Redis for distributed rate limiting
storage_uri = settings.rate_limit_redis_url if settings.rate_limit_enabled else "memory://"

limiter = Limiter(
    key_func=get_combined_key,
    default_limits=[f"{settings.rate_limit_per_min}/minute"] if settings.rate_limit_enabled else [],
    storage_uri=storage_uri,
    strategy="fixed-window",  # or "moving-window" for smoother limits
)

# ============================================================
# Dynamic Limit Calculation
# ============================================================

def get_limit_for_request(request: Request, base_limit: str) -> str:
    """
    Calculate effective rate limit based on user role.
    base_limit format: "N/period" (e.g., "100/minute")
    """
    if not settings.rate_limit_enabled:
        return "1000000/minute"  # effectively unlimited
    
    try:
        # Parse base limit
        parts = base_limit.split("/")
        count = int(parts[0])
        period = parts[1] if len(parts) > 1 else "minute"
        
        # Get user role
        role = "Client"
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            from app.core.security import decode_token
            payload = decode_token(auth.removeprefix("Bearer ").strip())
            role = payload.get("role", "Client")
        
        # Apply multiplier
        multiplier = ROLE_MULTIPLIERS.get(role, 1.0)
        effective_count = max(1, int(count * multiplier))
        
        return f"{effective_count}/{period}"
    except Exception:
        return base_limit

# ============================================================
# Rate Limit Decorators for Easy Use
# ============================================================

def rate_limit(limit_key: str):
    """Decorator to apply a named rate limit."""
    def decorator(func):
        limit = RATE_LIMITS.get(limit_key, "100/minute")
        return limiter.limit(limit)(func)
    return decorator

def rate_limit_dynamic(limit_key: str):
    """Decorator with dynamic role-based multiplier."""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            limit = get_limit_for_request(request, RATE_LIMITS.get(limit_key, "100/minute"))
            # Apply limit dynamically
            limited_func = limiter.limit(limit)(func)
            return await limited_func(request, *args, **kwargs)
        return wrapper
    return decorator

# ============================================================
# Manual Rate Limit Check (for programmatic use)
# ============================================================

async def check_rate_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
    """
    Manually check rate limit without decorator.
    Returns (allowed, current_count, remaining).
    """
    if not settings.rate_limit_enabled:
        return True, 0, limit
    
    redis = get_redis()
    redis_key = f"ratelimit:{key}"
    
    pipe = redis.pipeline()
    pipe.incr(redis_key)
    pipe.ttl(redis_key)
    results = await pipe.execute()
    
    current = results[0]
    ttl = results[1]
    
    if current == 1:
        # First request, set expiry
        await redis.expire(redis_key, window_seconds)
        ttl = window_seconds
    
    allowed = current <= limit
    remaining = max(0, limit - current)
    
    return allowed, current, remaining

async def get_rate_limit_headers(key: str, limit: int, window_seconds: int) -> dict:
    """Get standard rate limit headers for response."""
    allowed, current, remaining = await check_rate_limit(key, limit, window_seconds)
    reset = window_seconds  # approximate
    
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset),
        "Retry-After": str(window_seconds) if not allowed else "",
    }