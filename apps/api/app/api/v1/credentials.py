from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime, timezone, date
import uuid
from pydantic import BaseModel, Field, validator
from app.schemas.common import FirestoreOut
from app.infra.firestore.client import get_db
from app.infra.secrets.client import encrypt_value, decrypt_value, mask_value
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission

router = APIRouter()

# ── Portal catalog (per-client password checklist) ───────────────
# Standard statutory / firm portals whose credentials we collect from clients.
PORTAL_CATALOG: dict[str, dict] = {
    "it_efiling":    {"label": "IT e-Filing / PAN", "url": "https://www.incometax.gov.in", "expiry_hint": "Change every 6 months (65/89-day rule on IT portal)"},
    "tan":           {"label": "TAN", "url": "https://www.incometax.gov.in/tan", "expiry_hint": "Same password cycle as IT e-Filing portal"},
    "traces":        {"label": "TRACES", "url": "https://www.tdscpc.gov.in", "expiry_hint": "Password valid 180 days — reset proactively"},
    "gst":           {"label": "GST", "url": "https://www.gst.gov.in", "expiry_hint": "Advisor login — password rotates on Auth OTP reset"},
    "epfo":          {"label": "EPFO", "url": "https://unifiedportal-mem.epfindia.gov.in", "expiry_hint": "Establishment login — periodic reset"},
    "esic":          {"label": "ESIC", "url": "https://www.esic.gov.in", "expiry_hint": "Employer login — periodic reset"},
    "pt":            {"label": "PT (Professional Tax)", "url": "https://eservices.treasury.karnataka.gov.in", "expiry_hint": "State-wise portal — collect enrolment credentials"},
    "fla":           {"label": "FLA (RBI return)", "url": "https://fla.rbi.org.in", "expiry_hint": "Annual return login — reset on anniversary"},
    "firms_portal":  {"label": "Firms Portal (MCA/ROC)", "url": "https://www.mca.gov.in", "expiry_hint": "DSC + password — DSC not stored in vault"},
    "icegate":       {"label": "ICEGATE (Customs)", "url": "https://www.icegate.gov.in", "expiry_hint": "IEC login — periodic password reset"},
    "accounting":    {"label": "Accounting Software", "url": "", "expiry_hint": "TallyPrime / QuickBooks / Zoho Books admin"},
    "startup_india": {"label": "Startup India", "url": "https://www.startupindia.gov.in", "expiry_hint": "Recognised start-up portal login"},
    "iec":           {"label": "IEC (Import-Export Code)", "url": "https://dgft.gov.in", "expiry_hint": "DGFT IEC login"},
    "trade_licence": {"label": "Trade Licence", "url": "", "expiry_hint": "Municipal / urban local body trade licence portal"},
    "fssai":         {"label": "FSSAI", "url": "https://foscos.fssai.gov.in", "expiry_hint": "Food licence login — periodic reset"},
}
PORTAL_KEYS = list(PORTAL_CATALOG.keys())

EXPIRE_SOON_DAYS = 30  # password flagged as due for change within this window


def _expiry_status(expires_at: Optional[str]):
    """Return (days_to_expiry, expiry_status) for an expiry date."""
    if not expires_at:
        return None, None
    try:
        d = date.fromisoformat(expires_at[:10])
    except (ValueError, TypeError):
        return None, None
    days = (d - date.today()).days
    if days < 0:
        return days, "expired"
    if days <= EXPIRE_SOON_DAYS:
        return days, "expiring_soon"
    return days, "ok"


class CredentialCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    client_id: Optional[str] = None
    portal: Optional[str] = None
    url: Optional[str] = None
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    notes: Optional[str] = None
    expires_at: Optional[str] = Field(None, description="YYYY-MM-DD — when this password should be rotated")

    @validator('portal')
    def validate_portal(cls, v):
        if v and v not in PORTAL_CATALOG:
            raise ValueError(f"portal must be one of {PORTAL_KEYS}")
        return v

    @validator('expires_at')
    def validate_expires_at(cls, v):
        if v:
            try:
                date.fromisoformat(v[:10])
            except ValueError:
                raise ValueError('expires_at must be ISO format YYYY-MM-DD')
        return v


class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    portal: Optional[str] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None
    expires_at: Optional[str] = None

    @validator('portal')
    def validate_portal(cls, v):
        if v and v not in PORTAL_CATALOG:
            raise ValueError(f"portal must be one of {PORTAL_KEYS}")
        return v

    @validator('expires_at')
    def validate_expires_at(cls, v):
        if v:
            try:
                date.fromisoformat(v[:10])
            except ValueError:
                raise ValueError('expires_at must be ISO format YYYY-MM-DD')
        return v


class CredentialListResponse(FirestoreOut):
    """List response — never exposes plaintext password."""
    id: str
    tenant_id: str
    client_id: Optional[str] = None
    portal: Optional[str] = None
    portal_label: Optional[str] = None
    name: str
    url: Optional[str] = None
    username_masked: str
    username_full: Optional[str] = None
    url_domain: Optional[str] = None
    notes: Optional[str] = None
    expires_at: Optional[str] = None
    days_to_expiry: Optional[int] = None
    expiry_status: Optional[str] = None  # expired | expiring_soon | ok
    created_at: str
    updated_at: Optional[str] = None
    last_accessed_at: Optional[str] = None
    access_count: int = 0


class CredentialRevealResponse(FirestoreOut):
    """Reveal response — exposes plaintext ONCE (audit logged)."""
    id: str
    name: str
    portal: Optional[str] = None
    username: str
    password: str
    url: Optional[str] = None
    notes: Optional[str] = None
    expires_at: Optional[str] = None
    revealed_at: str


def _to_list_response(data: dict) -> CredentialListResponse:
    """Build a list response (masked) from a raw credential doc dict."""
    expires_at = data.get("expires_at")
    days, status = _expiry_status(expires_at)
    return CredentialListResponse(
        id=data["id"],
        tenant_id=data["tenant_id"],
        client_id=data.get("client_id"),
        portal=data.get("portal"),
        portal_label=PORTAL_CATALOG.get(data.get("portal"), {}).get("label") if data.get("portal") else None,
        name=data["name"],
        url=data.get("url"),
        username_masked=mask_value(data["usernameEnc"]),
        notes=data.get("notes"),
        expires_at=expires_at,
        days_to_expiry=days,
        expiry_status=status,
        created_at=data["created_at"],
        updated_at=data.get("updated_at"),
        last_accessed_at=data.get("last_accessed_at"),
        access_count=data.get("access_count", 0),
    )


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
        "portal": body.portal,
        "name": body.name,
        "url": body.url,
        "usernameEnc": encrypt_value(body.username),
        "passwordEnc": encrypt_value(body.password),
        "notes": body.notes,
        "expires_at": body.expires_at,
        "created_at": now,
        "updated_at": None,
        "last_accessed_at": None,
        "access_count": 0,
    }
    db.collection("credentials").document(cred_id).set(cred)

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="CREATE", entity="credentials", entity_id=cred_id, diff={"name": body.name, "portal": body.portal})

    return _to_list_response(cred)


@router.get("/portals")
async def list_portals(
    _: None = Depends(require_permission("credentials", "view"))
):
    """Return the fixed portal catalog (label, default URL, expiry hint)."""
    return {
        "portals": [
            {"key": k, "label": v["label"], "url": v["url"], "expiry_hint": v["expiry_hint"]}
            for k, v in PORTAL_CATALOG.items()
        ],
        "default_expire_days": EXPIRE_SOON_DAYS,
    }


@router.get("/checklist")
async def client_password_checklist(
    client_id: str,
    _: None = Depends(require_permission("credentials", "view"))
):
    """Per-client checklist: which portal passwords are collected vs still pending from the client."""
    db = get_db()
    tenant_id = get_current_tenant()

    cdoc = db.collection("clients").document(client_id).get()
    if not cdoc.exists or cdoc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Client not found")

    docs = list(db.collection("credentials").where("tenant_id", "==", tenant_id).stream())
    by_portal: dict[str, list[dict]] = {k: [] for k in PORTAL_KEYS}
    firm_level: list[dict] = []
    for d in docs:
        data = d.to_dict()
        days, status = _expiry_status(data.get("expires_at"))
        item = {
            "id": d.id,
            "name": data.get("name"),
            "portal": data.get("portal"),
            "username_masked": mask_value(data.get("usernameEnc", "")),
            "expires_at": data.get("expires_at"),
            "days_to_expiry": days,
            "expiry_status": status,
        }
        if data.get("client_id") == client_id and data.get("portal"):
            by_portal[data["portal"]].append(item)
        elif data.get("client_id") == client_id:
            firm_level.append(item)  # collected for this client but uncategorized

    entries = []
    for k in PORTAL_KEYS:
        items = by_portal[k]
        entries.append({
            "portal": k,
            "label": PORTAL_CATALOG[k]["label"],
            "url": PORTAL_CATALOG[k]["url"],
            "expiry_hint": PORTAL_CATALOG[k]["expiry_hint"],
            "collected": len(items) > 0,
            "count": len(items),
            "credentials": items,
        })

    return {
        "client_id": client_id,
        "client_name": cdoc.to_dict().get("name", "Unknown"),
        "portals": entries,
        "collected_count": sum(1 for e in entries if e["collected"]),
        "pending_count": sum(1 for e in entries if not e["collected"]),
        "total": len(PORTAL_KEYS),
        "other_credentials": firm_level,
    }


@router.get("/", response_model=List[CredentialListResponse])
async def list_credentials(
    client_id: Optional[str] = None,
    portal: Optional[str] = None,
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
        if portal and data.get("portal") != portal:
            continue
        data["id"] = d.id
        out.append(_to_list_response(data))
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
        id=cred_id, name=data["name"], portal=data.get("portal"),
        username=username_plain, password=password_plain,
        url=data.get("url"), notes=data.get("notes"),
        expires_at=data.get("expires_at"), revealed_at=now,
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
    data["id"] = cred_id
    return _to_list_response(data)


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