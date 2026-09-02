from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import agent as agent_router
from app.api.v1 import audit as audit_router
from app.api.v1 import auth as auth_router
from app.api.v1 import bd as bd_router
from app.api.v1 import billing as billing_router
from app.api.v1 import clients as clients_router
from app.api.v1 import compliance as compliance_router
from app.api.v1 import credentials as credentials_router
from app.api.v1 import documents as documents_router
from app.api.v1 import health as health_router
from app.api.v1 import reports as reports_router
from app.api.v1 import support as support_router
from app.api.v1 import tasks as tasks_router
from app.core.audit import audit_middleware
from app.core.config import get_settings
from app.core.tenant import tenant_middleware
from app.core.rate_limit import limiter, _rate_limit_exceeded_handler
from app.core.bot_protection import BotDetectionMiddleware
from slowapi.errors import RateLimitExceeded


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request payload size."""
    def __init__(self, app, max_size_mb: int = 10):
        super().__init__(app)
        self.max_size = max_size_mb * 1024 * 1024
    
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload too large. Maximum size is {self.max_size // (1024*1024)}MB."}
            )
        return await call_next(request)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Add request timeout."""
    def __init__(self, app, timeout_seconds: int = 30):
        super().__init__(app)
        self.timeout = timeout_seconds
    
    async def dispatch(self, request: Request, call_next):
        import asyncio
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"detail": f"Request timeout after {self.timeout} seconds"}
            )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title='CAOMS API',
        description='CAOMS API',
        version='0.2.0',
        docs_url='/docs',
        redoc_url='/redoc',
        openapi_url='/openapi.json',
    )
    
    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
    
    # Security Middleware (order matters - outermost first)
    # 1. Payload size limit
    app.add_middleware(PayloadSizeLimitMiddleware, max_size_mb=settings.max_payload_size_mb)
    # 2. Request timeout
    app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=settings.request_timeout_seconds)
    # 3. Rate limiting
    if settings.rate_limit_enabled:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # 4. Bot detection (logs suspicious requests, doesn't block)
    if settings.bot_protection_enabled:
        app.add_middleware(BotDetectionMiddleware)
    # 5. Tenant resolution
    app.middleware('http')(tenant_middleware)
    # 6. Audit logging (innermost)
    app.middleware('http')(audit_middleware)
    
    try:
        Instrumentator().instrument(app).expose(app, endpoint='/metrics')
    except Exception:
        pass
    
    app.include_router(auth_router.router, prefix='/api/v1/auth', tags=['auth'])
    app.include_router(health_router.router, tags=['health'])
    app.include_router(clients_router.router, prefix='/api/v1/clients', tags=['clients'])
    app.include_router(tasks_router.router, prefix='/api/v1/tasks', tags=['tasks'])
    app.include_router(compliance_router.router, prefix='/api/v1/compliance', tags=['compliance'])
    app.include_router(documents_router.router, prefix='/api/v1/documents', tags=['documents'])
    app.include_router(credentials_router.router, prefix='/api/v1/credentials', tags=['credentials'])
    app.include_router(billing_router.router, prefix='/api/v1/billing', tags=['billing'])
    app.include_router(agent_router.router, prefix='/api/v1/agent', tags=['agent'])
    app.include_router(audit_router.router, prefix='/api/v1/audit', tags=['audit'])
    app.include_router(reports_router.router, prefix='/api/v1/reports', tags=['reports'])
    app.include_router(bd_router.router, prefix='/api/v1/bd', tags=['bd'])
    app.include_router(support_router.router, prefix='/api/v1/support', tags=['support'])

    @app.get('/', tags=['root'])
    async def root():
        return {'name': 'CAOMS API', 'version': '0.2.0', 'tenant_mode': settings.tenant_mode, 'docs': '/docs', 'health': '/health'}

    return app


app = create_app()
