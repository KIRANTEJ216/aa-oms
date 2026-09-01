from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.common import FirestoreOut
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission

router = APIRouter()

class AuditEntry(BaseModel):
    id: str
    actorId: Optional[str] = None
    action: Optional[str] = None
    entity: Optional[str] = None
    entityId: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    ip: Optional[str] = None
    userAgent: Optional[str] = None
    statusCode: Optional[int] = None
    createdAt: Optional[str] = None

class AuditListResponse(FirestoreOut):
    total: int
    items: List[AuditEntry]


@router.get("/logs", response_model=AuditListResponse)
async def list_audit_logs(
    limit: int = 100,
    entity: Optional[str] = None,
    action: Optional[str] = None,
    _: None = Depends(require_permission("audit", "view"))
):
    """List immutable audit logs, newest first, scoped to current tenant."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("auditLogs").where("tenant_id", "==", tenant_id).stream())

    entries = []
    for d in docs:
        data = d.to_dict() or {}
        if entity and data.get("entity") != entity:
            continue
        if action and data.get("action") != action:
            continue
        created = data.get("createdAt")
        created_str = created.isoformat() if hasattr(created, "isoformat") else str(created) if created else None
        entries.append(AuditEntry(
            id=d.id,
            actorId=data.get("actorId"),
            action=data.get("action"),
            entity=data.get("entity"),
            entityId=data.get("entityId"),
            method=data.get("method"),
            path=data.get("path"),
            ip=data.get("ip"),
            userAgent=data.get("userAgent"),
            statusCode=data.get("statusCode"),
            createdAt=created_str,
        ))

    entries.sort(key=lambda e: e.createdAt or "", reverse=True)
    items = entries[:limit]
    return AuditListResponse(total=len(entries), items=items)
