from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import base64
from pydantic import BaseModel, Field
from app.schemas.common import FirestoreOut
from app.infra.firestore.client import get_db
from app.infra.gcs.client import (
    upload_object, download_object, delete_object,
    generate_signed_url, verify_signed_url,
)
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission

router = APIRouter()

# 7 default folders per client (PDF p.12 standard)
DEFAULT_FOLDERS = [
    "KYC Documents",
    "Financial Statements",
    "Tax Documents",
    "GST Documents",
    "Correspondence",
    "Agreements",
    "Bank Documents",
]

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# ── Schemas ───────────────────────────────────────────────────────
class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None

class DocumentUploadRequest(BaseModel):
    client_id: str
    folder_id: str
    name: str = Field(..., min_length=1, max_length=200)
    content_base64: str = Field(..., description="Base64-encoded file content")
    content_type: str = Field("application/octet-stream")
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

class DocumentVersionUpload(BaseModel):
    content_base64: str
    content_type: str = "application/octet-stream"
    notes: Optional[str] = None

class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None

class DocumentShareCreate(BaseModel):
    mode: str = Field("View Only", description="View Only | Download Enabled")
    expiry_days: int = Field(7, ge=1, le=90)

class FolderResponse(FirestoreOut):
    id: str
    name: str
    parent_id: Optional[str] = None
    path: str
    client_id: Optional[str] = None

class DocumentResponse(FirestoreOut):
    id: str
    tenant_id: str
    client_id: str
    folder_id: str
    name: str
    size: int
    content_type: str
    tags: List[str]
    version: int
    gcs_key: str
    is_shared: bool
    share_mode: Optional[str] = None
    share_expiry: Optional[str] = None
    uploaded_by: Optional[str]
    created_at: str
    updated_at: Optional[str] = None

class DocumentVersionResponse(FirestoreOut):
    version: int
    size: int
    uploaded_by: Optional[str]
    uploaded_at: str
    notes: Optional[str] = None

class DocumentShareResponse(FirestoreOut):
    id: str
    document_id: str
    mode: str
    expiry: str
    share_url: str


def _ensure_default_folders(db, tenant_id: str, client_id: str) -> List[dict]:
    """Create the 7 default folders for a client if they don't exist."""
    existing = list(db.collection("documentFolders")
                    .where("tenant_id", "==", tenant_id)
                    .where("client_id", "==", client_id).stream())
    if existing:
        return [d.to_dict() | {"id": d.id} for d in existing]

    folders = []
    for name in DEFAULT_FOLDERS:
        fid = str(uuid.uuid4())
        fdoc = {
            "id": fid,
            "tenant_id": tenant_id,
            "client_id": client_id,
            "name": name,
            "parent_id": None,
            "path": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        db.collection("documentFolders").document(fid).set(fdoc)
        folders.append(fdoc)
    return folders


# ── Folder routes ─────────────────────────────────────────────────

@router.get("/folders/{client_id}", response_model=List[FolderResponse])
async def list_folders(
    client_id: str,
    _: None = Depends(require_permission("documents", "view"))
):
    """List all folders for a client (creates the 7 default folders on first access)."""
    db = get_db()
    tenant_id = get_current_tenant()
    client_doc = db.collection("clients").document(client_id).get()
    if not client_doc.exists or client_doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Client not found")
    folders = _ensure_default_folders(db, tenant_id, client_id)
    return [FolderResponse(**f) for f in folders]


@router.post("/folders/{client_id}", response_model=FolderResponse)
async def create_folder(
    client_id: str,
    body: FolderCreate,
    _: None = Depends(require_permission("documents", "create"))
):
    """Create a custom sub-folder under a client."""
    db = get_db()
    tenant_id = get_current_tenant()
    client_doc = db.collection("clients").document(client_id).get()
    if not client_doc.exists or client_doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Client not found")

    fid = str(uuid.uuid4())
    # Compute path (parent_path / name)
    parent_path = ""
    if body.parent_id:
        pdoc = db.collection("documentFolders").document(body.parent_id).get()
        if pdoc.exists:
            parent_path = pdoc.to_dict().get("path", "") + "/"
    fdoc = {
        "id": fid,
        "tenant_id": tenant_id,
        "client_id": client_id,
        "name": body.name,
        "parent_id": body.parent_id,
        "path": parent_path + body.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.collection("documentFolders").document(fid).set(fdoc)
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="CREATE", entity="documentFolders", entity_id=fid)
    return FolderResponse(**fdoc)


# ── Document routes ──────────────────────────────────────────────

@router.get("/download")
async def download_signed(
    key: str = Query(...),
    exp: str = Query(...),
    sig: str = Query(...),
):
    """Download a file via a signed share link (no auth required — token is the credential)."""
    if not verify_signed_url(key, exp, sig):
        raise HTTPException(status_code=403, detail="Share link expired or invalid")
    try:
        data = download_object(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    ct = "application/octet-stream"
    if key.lower().endswith(".pdf"): ct = "application/pdf"
    elif key.lower().endswith((".png", ".jpg", ".jpeg")): ct = "image/jpeg"
    elif key.lower().endswith(".txt"): ct = "text/plain"
    return Response(content=data, media_type=ct, headers={"Content-Disposition": f"attachment; filename={key.split('/')[-1]}"})


@router.get("/by-client/{client_id}", response_model=List[DocumentResponse])
async def list_documents(
    client_id: str,
    folder_id: Optional[str] = None,
    _: None = Depends(require_permission("documents", "view"))
):
    """List documents for a client, optionally filtered by folder."""
    db = get_db()
    tenant_id = get_current_tenant()
    # Ensure default folders exist
    _ensure_default_folders(db, tenant_id, client_id)
    # Query documents
    docs = list(db.collection("documents")
                .where("tenant_id", "==", tenant_id)
                .where("client_id", "==", client_id).stream())
    results = []
    for d in docs:
        data = d.to_dict() | {"id": d.id}
        if folder_id and data.get("folder_id") != folder_id:
            continue
        results.append(DocumentResponse(**data))
    return results


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    body: DocumentUploadRequest,
    _: None = Depends(require_permission("documents", "create"))
):
    """Upload a new document (version 1)."""
    db = get_db()
    tenant_id = get_current_tenant()

    # Verify client
    client_doc = db.collection("clients").document(body.client_id).get()
    if not client_doc.exists or client_doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify folder belongs to client
    folder_doc = db.collection("documentFolders").document(body.folder_id).get()
    if not folder_doc.exists or folder_doc.to_dict().get("client_id") != body.client_id:
        raise HTTPException(status_code=400, detail="Folder not found or doesn't belong to client")

    # Decode file
    try:
        data = base64.b64decode(body.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large ({len(data)} bytes). Max {MAX_FILE_SIZE // (1024*1024)}MB.")

    # Build GCS key
    doc_id = str(uuid.uuid4())
    folder_path = folder_doc.to_dict().get("path", "root").replace(" ", "_")
    gcs_key = f"tenants/{tenant_id}/clients/{body.client_id}/{folder_path}/{doc_id}_v1_{body.name}"

    # Upload to GCS (stub)
    upload_object(gcs_key, data, body.content_type)

    # Save document + version 1
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": doc_id,
        "tenant_id": tenant_id,
        "client_id": body.client_id,
        "folder_id": body.folder_id,
        "name": body.name,
        "size": len(data),
        "content_type": body.content_type,
        "tags": body.tags,
        "version": 1,
        "gcs_key": gcs_key,
        "is_shared": False,
        "uploaded_by": "system",
        "created_at": now,
        "updated_at": now,
    }
    db.collection("documents").document(doc_id).set(doc)
    db.collection("documents").document(doc_id).collection("versions").document("1").set({
        "version": 1,
        "size": len(data),
        "gcs_key": gcs_key,
        "uploaded_by": "system",
        "uploaded_at": now,
        "notes": body.notes,
    })

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="CREATE", entity="documents", entity_id=doc_id)

    return DocumentResponse(**doc)


@router.post("/{doc_id}/version", response_model=DocumentVersionResponse)
async def upload_version(
    doc_id: str,
    body: DocumentVersionUpload,
    _: None = Depends(require_permission("documents", "update"))
):
    """Upload a new version of an existing document (bump version, keep old in versions subcollection)."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("documents").document(doc_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        data = base64.b64decode(body.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large ({len(data)} bytes)")

    current = doc.to_dict()
    new_version = current.get("version", 1) + 1
    gcs_key = current["gcs_key"].rsplit("/", 1)[0] + f"/{doc_id}_v{new_version}_{current['name']}"
    upload_object(gcs_key, data, body.content_type)

    now = datetime.now(timezone.utc).isoformat()
    version_doc = {
        "version": new_version,
        "size": len(data),
        "gcs_key": gcs_key,
        "uploaded_by": "system",
        "uploaded_at": now,
        "notes": body.notes,
    }
    db.collection("documents").document(doc_id).collection("versions").document(str(new_version)).set(version_doc)
    doc_ref.update({"version": new_version, "size": len(data), "gcs_key": gcs_key, "updated_at": now})

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="VERSION_UPLOAD", entity="documents", entity_id=doc_id, diff={"new_version": new_version})

    return DocumentVersionResponse(**{k: version_doc[k] for k in ("version", "size", "uploaded_by", "uploaded_at", "notes")})


@router.get("/{doc_id}/versions", response_model=List[DocumentVersionResponse])
async def list_versions(
    doc_id: str,
    _: None = Depends(require_permission("documents", "view"))
):
    """List all versions of a document."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("documents").document(doc_id).get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")
    versions = list(db.collection("documents").document(doc_id).collection("versions").stream())
    out = []
    for v in versions:
        d = v.to_dict()
        out.append(DocumentVersionResponse(
            version=d["version"], size=d["size"], uploaded_by=d.get("uploaded_by"),
            uploaded_at=d["uploaded_at"], notes=d.get("notes")
        ))
    return sorted(out, key=lambda x: x.version)


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str,
    body: DocumentUpdate,
    _: None = Depends(require_permission("documents", "update"))
):
    """Update document metadata (name/folder/tags/notes)."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("documents").document(doc_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc_ref.update(update_data)
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="UPDATE", entity="documents", entity_id=doc_id)
    return DocumentResponse(**(doc.to_dict() | update_data | {"id": doc_id}))


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    _: None = Depends(require_permission("documents", "delete"))
):
    """Soft-delete a document (mark inactive)."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("documents").document(doc_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")
    doc_ref.update({
        "is_active": False,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    })
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="DELETE", entity="documents", entity_id=doc_id)
    return {"message": "Document deleted"}


@router.post("/{doc_id}/share", response_model=DocumentShareResponse)
async def create_share_link(
    doc_id: str,
    body: DocumentShareCreate,
    _: None = Depends(require_permission("documents", "export"))
):
    """Generate a time-limited share link for client portal access."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("documents").document(doc_id).get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    from datetime import timedelta
    expiry = datetime.now(timezone.utc) + timedelta(days=body.expiry_days)
    share_id = str(uuid.uuid4())
    signed = generate_signed_url(doc.to_dict()["gcs_key"], body.expiry_days * 24 * 60)
    share_doc = {
        "id": share_id,
        "tenant_id": tenant_id,
        "document_id": doc_id,
        "mode": body.mode,
        "expiry": expiry.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.collection("documentShares").document(share_id).set(share_doc)
    doc_ref = db.collection("documents").document(doc_id)
    doc_ref.update({"is_shared": True, "share_mode": body.mode, "share_expiry": expiry.isoformat()})

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="SHARE_CREATE", entity="documents", entity_id=doc_id, diff={"mode": body.mode, "expiry_days": body.expiry_days})

    return DocumentShareResponse(
        id=share_id, document_id=doc_id, mode=body.mode, expiry=expiry.isoformat(), share_url=signed
    )
