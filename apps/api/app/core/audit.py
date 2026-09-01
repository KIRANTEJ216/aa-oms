from fastapi import Request
from datetime import datetime, timezone
import uuid
from app.core.tenant import get_current_tenant
from app.infra.firestore.client import get_db

async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    # Only log mutating or auth actions
    path = request.url.path
    method = request.method
    should_log = (
        (path.startswith("/api/v1/auth/") and method == "POST") or
        (path.startswith("/api/v1/") and method in ("POST","PUT","PATCH","DELETE"))
    )
    if should_log:
        try:
            db = get_db()
            # Resolve actor from JWT if present
            actor_id = None
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                try:
                    from app.core.security import decode_token
                    payload = decode_token(auth.removeprefix("Bearer ").strip())
                    actor_id = payload.get("sub")
                except Exception:
                    pass
            tid = ""
            try:
                tid = get_current_tenant()
            except Exception:
                tid = request.headers.get("X-Tenant-ID", "")
            action = {"POST":"CREATE","PUT":"UPDATE","PATCH":"UPDATE","DELETE":"DELETE"}.get(method, "CREATE")
            if "/auth/login" in path: action = "LOGIN"
            elif "/auth/" in path: action = "AUTH"
            elif "/credentials" in path and "reveal" in path: action = "VIEW_CREDENTIAL"
            elif method == "GET" and "export" in path: action = "EXPORT"
            db.collection("auditLogs").document(str(uuid.uuid4())).set({
                "tenant_id": tid,
                "actorId": actor_id,
                "action": action,
                "entity": path.split("/")[3] if len(path.split("/"))>3 else path,
                "entityId": path.split("/")[-1] if path.split("/")[-1] not in ("login","register","mfa","verify") else None,
                "method": method,
                "path": path,
                "ip": request.client.host if request.client else None,
                "userAgent": request.headers.get("user-agent"),
                "statusCode": response.status_code,
                "createdAt": datetime.now(timezone.utc),
            })
        except Exception:
            # Never break the request on audit failure
            pass
    return response

async def log_audit(*, tenant_id: str, actor_id: str | None, action: str, entity: str, entity_id: str | None = None, diff: dict | None = None, ip: str | None = None):
    try:
        db = get_db()
        db.collection("auditLogs").document(str(uuid.uuid4())).set({
            "tenant_id": tenant_id, "actorId": actor_id, "action": action, "entity": entity, "entityId": entity_id, "diff": diff, "ip": ip, "createdAt": datetime.now(timezone.utc),
        })
    except Exception:
        pass
