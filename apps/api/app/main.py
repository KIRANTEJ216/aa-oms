from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import agent as agent_router
from app.api.v1 import audit as audit_router
from app.api.v1 import auth as auth_router
from app.api.v1 import billing as billing_router
from app.api.v1 import clients as clients_router
from app.api.v1 import compliance as compliance_router
from app.api.v1 import credentials as credentials_router
from app.api.v1 import documents as documents_router
from app.api.v1 import health as health_router
from app.api.v1 import tasks as tasks_router
from app.core.audit import audit_middleware
from app.core.config import get_settings
from app.core.tenant import tenant_middleware


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
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
    app.middleware('http')(tenant_middleware)
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

    @app.get('/', tags=['root'])
    async def root():
        return {'name': 'CAOMS API', 'version': '0.2.0', 'tenant_mode': settings.tenant_mode, 'docs': '/docs', 'health': '/health'}

    return app

app = create_app()
