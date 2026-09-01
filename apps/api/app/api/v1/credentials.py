from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field
from app.infra.firestore.client import get_db
from app.infra.secrets.client import encrypt_value, decrypt_value, mask_value
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission

router = APIRouter()


class CredentialCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    client_id: Optional[str] = None
    url: Optional[str] = None
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    notes: Optional[str] = None


class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None


class CredentialListResponse(BaseModel):
    """List response — never exposes plaintext password."""
    id: str
    tenant_id: str
    client_id: Optional[str] = None
    name: str
    url: Optional[str] = None
    username_masked: str
    username_full: Optional[str] = None
    url_domain: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    last_accessed_at: Optional[str] = None
    access_count: int = 0


class CredentialRevealResponse(BaseModel):
    """Reveal response — exposes plaintext ONCE (audit logged)."""
    id: str
    name: str
    username: str
    password: str
    url: Optional[str] = None
    notes: Optional[str] = None
    revealed_at: str


@router.post("/", response_model=CredentialListResponse, status_code=201)
async def create_credential(
    body: CredentialCreate,
    _: None = Depends(require_permission("credentials", "create"))
):
    """Encrypt and store a new credential."""
    db = get_db()
    tenant_id = get_current_tenant()

    # Verify client if provided
    if body.client_id:
        cdoc = db.collection("clients").document(body.client_id).get()
        if not cdoc.exists or cdoc.to_dict().get("tenant_id") != tenant_id:
            raise HTTPException(status_code=404, detail="Client not found")

    cred_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    cred = {
        "id": cred_id,
        "tenant_id": tenant_id,
        "client_id": body.client_id,
        "name": body.name,
        "url": body.url,
        "usernameEnc": encrypt_value(body.username),
        "passwordEnc": encrypt_value(body.password),
        "notes": body.notes,
        "created_at": now,
        "updated_at": None,
        "last_accessed_at": None,
        "access_count": 0,
    }
    db.collection("credentials").document(cred_id).set(cred)

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="CREATE", entity="credentials", entity_id=cred_id, diff={"name": body.name})

    return CredentialListResponse(
        id=cred_id, tenant_id=tenant_id, client_id=body.client_id, name=body.name,
        url=body.url, username_masked=mask_value(cred["usernameEnc"]),
        notes=body.notes, created_at=now, access_count=0,
    )


@router.get("/", response_model=List[CredentialListResponse])
async def list_credentials(
    client_id: Optional[str] = None,
    _: None = Depends(require_permission("credentials", "view"))
):
    """List credentials (passwords NEVER exposed — only masked username)."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("credentials").where("tenant_id", "==", tenant_id).stream())
    out = []
    for d in docs:
        data = d.to_dict()
        if client_id and data.get("client_id") != client_id:
            continue
        out.append(CredentialListResponse(
            id=d.id,
            tenant_id=data["tenant_id"],
            client_id=data.get("client_id"),
            name=data["name"],
            url=data.get("url"),
            username_masked=mask_value(data["usernameEnc"]),
            notes=data.get("notes"),
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
            last_accessed_at=data.get("last_accessed_at"),
            access_count=data.get("access_count", 0),
        ))
    return out


@router.post("/{cred_id}/reveal", response_model=CredentialRevealResponse)
async def reveal_credential(
    cred_id: str,
    _: None = Depends(require_permission("credentials", "view"))
):
    """Decrypt and return plaintext password ONCE — full audit trail logged."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("credentials").document(cred_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Credential not found")
    data = doc.to_dict()

    # Decrypt
    try:
        username_plain = decrypt_value(data["usernameEnc"])
        password_plain = decrypt_value(data["passwordEnc"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decryption failed: {e}")

    # Update access tracking
    now = datetime.now(timezone.utc).isoformat()
    doc_ref.update({
        "last_accessed_at": now,
        "access_count": data.get("access_count", 0) + 1,
    })

    # Log to credentialAccessLogs (specific to vault)
    log_id = str(uuid.uuid4())
    db.collection("credentialAccessLogs").document(log_id).set({
        "id": log_id,
        "tenant_id": tenant_id,
        "credential_id": cred_id,
        "credential_name": data["name"],
        "actor_id": "system",
        "action": "REVEAL",
        "ip": None,
        "accessed_at": now,
    })

    # Also log to immutable audit trail
    from app.core.audit import log_audit
    await log_audit(
        tenant_id=tenant_id, actor_id="system", action="VIEW_CREDENTIAL",
        entity="credentials", entity_id=cred_id,
        diff={"name": data["name"]}
    )

    return CredentialRevealResponse(
        id=cred_id, name=data["name"], username=username_plain, password=password_plain,
        url=data.get("url"), notes=data.get("notes"), revealed_at=now,
    )


@router.patch("/{cred_id}", response_model=CredentialListResponse)
async def update_credential(
    cred_id: str,
    body: CredentialUpdate,
    _: None = Depends(require_permission("credentials", "update"))
):
    """Update credential (re-encrypts on password change)."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("credentials").document(cred_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Credential not found")

    update_data = {}
    for k, v in body.dict().items():
        if v is None:
            continue
        if k == "password":
            update_data["passwordEnc"] = encrypt_value(v)
        elif k == "username":
            update_data["usernameEnc"] = encrypt_value(v)
        else:
            update_data[k] = v
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc_ref.update(update_data)

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="UPDATE", entity="credentials", entity_id=cred_id)

    data = doc.to_dict() | update_data
    return CredentialListResponse(
        id=cred_id, tenant_id=data["tenant_id"], client_id=data.get("client_id"),
        name=data["name"], url=data.get("url"),
        username_masked=mask_value(data["usernameEnc"]),
        notes=data.get("notes"), created_at=data["created_at"],
        updated_at=data.get("updated_at"), last_accessed_at=data.get("last_accessed_at"),
        access_count=data.get("access_count", 0),
    )


@router.delete("/{cred_id}")
async def delete_credential(
    cred_id: str,
    _: None = Depends(require_permission("credentials", "delete"))
):
    """Soft-delete a credential."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("credentials").document(cred_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Credential not found")
    doc_ref.update({
        "is_active": False,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    })
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="DELETE", entity="credentials", entity_id=cred_id)
    return {"message": "Credential deleted"}


@router.get("/access-logs")
async def list_access_logs(
    credential_id: Optional[str] = None,
    limit: int = 50,
    _: None = Depends(require_permission("credentials", "view"))
):
    """List vault access logs (every reveal is logged here + in auditLogs)."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("credentialAccessLogs").where("tenant_id", "==", tenant_id).stream())
    out = []
    for d in docs:
        data = d.to_dict()
        if credential_id and data.get("credential_id") != credential_id:
            continue
        out.append({
            "id": d.id,
            "credential_id": data.get("credential_id"),
            "credential_name": data.get("credential_name"),
            "actor_id": data.get("actor_id"),
            "action": data.get("action"),
            "ip": data.get("ip"),
            "accessed_at": data.get("accessed_at"),
        })
    out.sort(key=lambda x: x["accessed_at"], reverse=True)
    return out[:limit]
