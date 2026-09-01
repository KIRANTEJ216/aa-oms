from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from app.schemas.auth import RegisterRequest
from app.schemas.common import MessageResponse
from app.core.security import hash_password, verify_password
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant, SEED_TENANT_ID
from app.core.rbac import require_permission
from pydantic import BaseModel, Field, EmailStr, validator
import re

router = APIRouter()

# ── Schemas ──────────────────────────────────────────────────────
CLIENT_PAN_REGEX = r'^[A-Z]{5}[0-9]{4}[A-Z]$'
CLIENT_GSTIN_REGEX = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z$'
CLIENT_TAN_REGEX = r'^[A-Z]{4}[0-9]{5}[A-Z]$'

class ClientCreate(BaseModel):
    type: str = Field(..., description="Individual/HUF/Company/LLP/Trust")
    name: str = Field(..., min_length=2)
    pan: str = Field(..., min_length=10)
    gstin: str = Field("", min_length=0, max_length=15)
    tan: str = Field("", min_length=0, max_length=10)
    cin: str = Field("", min_length=0, max_length=21)
    llpin: str = Field("", min_length=0, max_length=10)
    email: EmailStr
    mobile: str = Field(..., min_length=10)
    address: str = Field(..., min_length=5)
    dob_or_incorporation: str = Field(..., description="Date of birth or incorporation date")
    engagement_manager: str = Field(..., description="Partner name / staff in charge")
    services: List[str] = Field(default_factory=list)
    is_portal_enabled: bool = False

    @validator('pan')
    def validate_pan(cls, v):
        if not re.match(CLIENT_PAN_REGEX, v):
            raise ValueError('Invalid PAN format. Expected: ABCDE1234F')
        return v.upper()

    @validator('gstin')
    def validate_gstin(cls, v):
        if v and not re.match(CLIENT_GSTIN_REGEX, v):
            raise ValueError('Invalid GSTIN format')
        return v.upper() if v else ""

    @validator('tan')
    def validate_tan(cls, v):
        if v and not re.match(CLIENT_TAN_REGEX, v):
            raise ValueError('Invalid TAN format')
        return v.upper() if v else ""

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    gstin: Optional[str] = None
    tan: Optional[str] = None
    address: Optional[str] = None
    engagement_manager: Optional[str] = None
    services: Optional[List[str]] = None
    is_portal_enabled: Optional[bool] = None

class ClientResponse(BaseModel):
    id: str
    tenant_id: str
    type: str
    name: str
    pan: str
    gstin: Optional[str]
    tan: Optional[str]
    cin: Optional[str]
    llpin: Optional[str]
    email: str
    mobile: str
    address: str
    engagement_manager: str
    services: List[str]
    is_portal_enabled: bool
    dob_or_incorporation: str
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


# ── Routes ───────────────────────────────────────────────────────

@router.get("/", response_model=List[ClientResponse])
async def list_clients(
    _: None = Depends(require_permission("clients", "view"))
):
    """List all clients for the current tenant."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("clients").where("tenant_id", "==", tenant_id).stream())
    return [
        ClientResponse(
            id=doc.id,
            **{k: v for k, v in doc.to_dict().items() if k != "id"}
        )
        for doc in docs
    ]

@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    client: ClientCreate,
    _: None = Depends(require_permission("clients", "create"))
):
    """Create a new client. PAN duplicate check enforced at DB level."""
    db = get_db()
    tenant_id = get_current_tenant()

    # Duplicate PAN check within tenant
    existing_docs = list(db.collection("clients").where("tenant_id", "==", tenant_id).where("pan", "==", client.pan).limit(1).stream())
    if existing_docs:
        # Always return 409 for duplicate PAN
        raise HTTPException(
            status_code=409,
            detail=f"PAN '{client.pan}' already exists for client '{existing_docs[0].to_dict().get('name', 'unknown')}'"
        )
        raise HTTPException(
            status_code=409,
            detail=f"PAN '{client.pan}' already exists for client '{existing[0].to_dict().get('name', 'unknown')}'"
        )

    client_id = str(uuid.uuid4())
    client_doc = {
        "id": client_id,
        "tenant_id": tenant_id,
        "type": client.type,
        "name": client.name,
        "pan": client.pan,
        "gstin": client.gstin,
        "tan": client.tan,
        "cin": client.cin,
        "llpin": client.llpin,
        "email": client.email,
        "mobile": client.mobile,
        "address": client.address,
        "engagement_manager": client.engagement_manager,
        "services": client.services,
        "is_portal_enabled": client.is_portal_enabled,
        "dob_or_incorporation": client.dob_or_incorporation,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
    }

    db.collection("clients").document(client_id).set(client_doc)
    
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id=client_id, action="CREATE", entity="clients", entity_id=client_id)
    
    return ClientResponse(**client_doc)

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    _: None = Depends(require_permission("clients", "view"))
):
    """Get a single client by ID."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("clients").document(client_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Client not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    return ClientResponse(**doc.to_dict())

@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    client_update: ClientUpdate,
    _: None = Depends(require_permission("clients", "update"))
):
    """Update a client."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("clients").document(client_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Client not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    
    update_data = {k: v for k, v in client_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    db.collection("clients").document(client_id).update(update_data)
    
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="UPDATE", entity="clients", entity_id=client_id)
    
    doc = db.collection("clients").document(client_id).get()
    return ClientResponse(**doc.to_dict())

@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    _: None = Depends(require_permission("clients", "delete"))
):
    """Soft-delete a client (mark as inactive)."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("clients").document(client_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Client not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    
    db.collection("clients").document(client_id).update({
        "is_active": False,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    })
    
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="DELETE", entity="clients", entity_id=client_id)
    return {"message": "Client deactivated successfully"}
