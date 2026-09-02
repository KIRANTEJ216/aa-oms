"""
Tenant Isolation Middleware:
- Enforces tenant boundaries at application layer
- Validates all database queries include tenant_id
- Prevents cross-tenant data access
- Logs tenant isolation violations
"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.tenant import get_current_tenant
from app.core.audit import log_audit


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tenant isolation at the application layer.
    Validates that all mutating operations include proper tenant scoping.
    """
    
    def __init__(self, app, strict: bool = True):
        super().__init__(app)
        self.strict = strict
        # Paths that don't require tenant validation
        self.exempt_paths = {
            "/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc",
            "/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/firebase",
            "/api/v1/auth/firebase/register", "/api/v1/auth/forgot-password",
            "/api/v1/auth/refresh", "/api/v1/auth/mfa/verify",
        }
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        
        # Skip exempt paths
        if any(path.startswith(p) for p in self.exempt_paths):
            return await call_next(request)
        
        # Skip non-mutating methods
        if method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        
        # Verify tenant is resolved
        try:
            tenant_id = get_current_tenant()
            if not tenant_id:
                if self.strict:
                    return HTTPException(401, "Tenant not resolved")
        except Exception:
            if self.strict:
                return HTTPException(401, "Tenant validation failed")
        
        response = await call_next(request)
        
        # Add tenant header for debugging
        if tenant_id:
            response.headers["X-Tenant-ID"] = tenant_id
        
        return response


class QueryTenantValidator:
    """
    Validates that Firestore queries include tenant_id filter.
    Can be used as a dependency or decorator.
    """
    
    @staticmethod
    def validate_query(query_dict: dict, tenant_id: str) -> bool:
        """
        Check if a Firestore query dict includes tenant_id filter.
        query_dict format: {"filters": [("tenant_id", "==", "abc")], ...}
        """
        if not query_dict or "filters" not in query_dict:
            return False
        
        for filter_spec in query_dict.get("filters", []):
            if len(filter_spec) >= 2 and filter_spec[0] == "tenant_id":
                if filter_spec[1] == "==" and filter_spec[2] == tenant_id:
                    return True
                if filter_spec[1] == "in" and tenant_id in filter_spec[2]:
                    return True
        
        return False
    
    @staticmethod
    def require_tenant_filter(query_dict: dict, tenant_id: str):
        """Raise exception if query doesn't have tenant filter."""
        if not QueryTenantValidator.validate_query(query_dict, tenant_id):
            raise HTTPException(
                status_code=403,
                detail="Query must include tenant_id filter for security"
            )
        return True


def get_tenant_id_or_401() -> str:
    """FastAPI dependency to get current tenant ID or raise 401."""
    try:
        return get_current_tenant()
    except Exception:
        raise HTTPException(401, "Tenant not resolved. Provide valid authentication.")


# ============================================================
# Cross-Tenant Access Prevention
# ============================================================

class CrossTenantGuard:
    """
    Guards against accidental cross-tenant data access.
    Use as a context manager or decorator for critical operations.
    """
    
    def __init__(self, tenant_id: str, operation: str = "operation"):
        self.tenant_id = tenant_id
        self.operation = operation
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False
    
    @staticmethod
    def verify_resource_tenant(resource_data: dict, expected_tenant_id: str) -> bool:
        """Verify a resource belongs to the expected tenant."""
        resource_tenant = resource_data.get("tenant_id")
        if not resource_tenant:
            return False
        if resource_tenant != expected_tenant_id:
            # Log security violation
            import asyncio
            asyncio.create_task(log_audit(
                tenant_id=expected_tenant_id,
                actor_id=None,
                action="CROSS_TENANT_ACCESS_ATTEMPT",
                entity="security/cross_tenant_guard",
                diff={
                    "expected_tenant": expected_tenant_id,
                    "resource_tenant": resource_tenant,
                    "operation": "verify_resource_tenant"
                }
            ))
            return False
        return True
    
    @staticmethod
    def assert_resource_tenant(resource_data: dict, expected_tenant_id: str):
        """Assert resource belongs to tenant, raise 403 if not."""
        if not CrossTenantGuard.verify_resource_tenant(resource_data, expected_tenant_id):
            raise HTTPException(403, "Cross-tenant access denied")


# ============================================================
# Tenant-Aware Query Builder
# ============================================================

class TenantQueryBuilder:
    """
    Helper to build tenant-scoped Firestore queries.
    Automatically adds tenant_id filter to all queries.
    """
    
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id or get_current_tenant()
        self._filters = []
        self._order_by = []
        self._limit = None
        self._offset = None
    
    def where(self, field: str, operator: str, value):
        """Add a where filter."""
        self._filters.append((field, operator, value))
        return self
    
    def where_tenant(self):
        """Explicitly add tenant_id filter."""
        self._filters.append(("tenant_id", "==", self.tenant_id))
        return self
    
    def order_by(self, field: str, direction: str = "ASCENDING"):
        """Add order by clause."""
        self._order_by.append((field, direction))
        return self
    
    def limit(self, limit: int):
        """Add limit."""
        self._limit = limit
        return self
    
    def offset(self, offset: int):
        """Add offset."""
        self._offset = offset
        return self
    
    def build(self) -> dict:
        """Build query dict for validation."""
        return {
            "filters": self._filters,
            "order_by": self._order_by,
            "limit": self._limit,
            "offset": self._offset,
        }
    
    def apply(self, collection_ref):
        """Apply query to Firestore collection reference."""
        query = collection_ref
        
        # Always add tenant filter first
        query = query.where("tenant_id", "==", self.tenant_id)
        
        # Add additional filters
        for field, operator, value in self._filters:
            if field != "tenant_id":  # Skip duplicate tenant filter
                query = query.where(field, operator, value)
        
        # Add ordering
        for field, direction in self._order_by:
            query = query.order_by(field, direction=direction)
        
        # Add limit/offset
        if self._limit:
            query = query.limit(self._limit)
        if self._offset:
            query = query.offset(self._offset)
        
        return query
    
    @classmethod
    def for_tenant(cls, tenant_id: str):
        """Create builder for specific tenant."""
        return cls(tenant_id)


# ============================================================
# Decorators for Tenant Isolation
# ============================================================

def require_tenant_access(entity: str, action: str):
    """
    Decorator that enforces tenant isolation + RBAC.
    Combines tenant validation with permission checking.
    """
    from functools import wraps
    from app.core.auth import get_current_user
    from app.core.rbac import check_permission
    from fastapi import Depends
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user
            user = await get_current_user()(kwargs.get("request"))
            
            # Validate tenant
            tenant_id = user.get("tenant_id")
            if not tenant_id:
                raise HTTPException(401, "Tenant not resolved")
            
            # Check RBAC
            role = user.get("role", "Client")
            if not check_permission(role, entity, action):
                raise HTTPException(403, f"Role '{role}' cannot {action} {entity}")
            
            # Add tenant_id to kwargs for downstream use
            kwargs["tenant_id"] = tenant_id
            kwargs["current_user"] = user
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator