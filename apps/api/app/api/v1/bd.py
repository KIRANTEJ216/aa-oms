from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime, timezone, date
import uuid
from pydantic import BaseModel, Field, EmailStr, validator
from app.schemas.common import FirestoreOut
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission
from app.core.security import decode_token

router = APIRouter()

LEAD_STATUSES = ["New", "Contacted", "Meeting Scheduled", "Proposal Sent", "Won", "Lost"]
LEAD_PRIORITIES = ["High", "Medium", "Low"]
LEAD_SOURCES = ["Referral", "Walk-in", "LinkedIn", "Website", "Cold Call", "Existing Client", "Other"]
FOLLOWUP_TYPES = ["Call", "Email", "Meeting", "Proposal", "Note"]


class LeadCreate(BaseModel):
    company_name: str = Field(..., min_length=2)
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    source: str = Field("Referral", description="Referral/Walk-in/LinkedIn/Website/Cold Call/Existing Client/Other")
    status: str = Field("New", description="New/Contacted/Meeting Scheduled/Proposal Sent/Won/Lost")
    priority: str = Field("Medium", description="High/Medium/Low")
    estimated_value: Optional[float] = Field(None, ge=0, description="Expected annual fees (INR)")
    services: List[str] = Field(default_factory=list)
    owner: str = Field(..., description="Partner / staff responsible")
    next_follow_up: Optional[str] = None
    notes: Optional[str] = None

    @validator('source')
    def validate_source(cls, v):
        if v and v not in LEAD_SOURCES:
            raise ValueError(f"source must be one of {LEAD_SOURCES}")
        return v

    @validator('status')
    def validate_status(cls, v):
        if v and v not in LEAD_STATUSES:
            raise ValueError(f"status must be one of {LEAD_STATUSES}")
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v and v not in LEAD_PRIORITIES:
            raise ValueError(f"priority must be one of {LEAD_PRIORITIES}")
        return v

    @validator('next_follow_up')
    def validate_next_follow_up(cls, v):
        if v:
            try:
                date.fromisoformat(v[:10])
            except ValueError:
                raise ValueError('next_follow_up must be ISO format YYYY-MM-DD')
        return v


class LeadUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    estimated_value: Optional[float] = None
    services: Optional[List[str]] = None
    owner: Optional[str] = None
    next_follow_up: Optional[str] = None
    notes: Optional[str] = None

    @validator('status')
    def validate_status(cls, v):
        if v and v not in LEAD_STATUSES:
            raise ValueError(f"status must be one of {LEAD_STATUSES}")
        return v

    @validator('next_follow_up')
    def validate_next_follow_up(cls, v):
        if v:
            try:
                date.fromisoformat(v[:10])
            except ValueError:
                raise ValueError('next_follow_up must be ISO format YYYY-MM-DD')
        return v


class LeadResponse(FirestoreOut):
    id: str
    tenant_id: str
    company_name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    status: str
    priority: str
    estimated_value: Optional[float] = None
    services: List[str] = []
    owner: str
    next_follow_up: Optional[str] = None
    is_overdue: bool = False
    notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class FollowUpCreate(BaseModel):
    type: str = Field("Call", description="Call/Email/Meeting/Proposal/Note")
    summary: str = Field(..., min_length=1)
    scheduled_for: Optional[str] = None

    @validator('type')
    def validate_type(cls, v):
        if v and v not in FOLLOWUP_TYPES:
            raise ValueError(f"type must be one of {FOLLOWUP_TYPES}")
        return v

    @validator('scheduled_for')
    def validate_scheduled_for(cls, v):
        if v:
            try:
                date.fromisoformat(v[:10])
            except ValueError:
                raise ValueError('scheduled_for must be ISO format YYYY-MM-DD')
        return v


class FollowUpResponse(FirestoreOut):
    id: str
    lead_id: str
    type: str
    summary: str
    scheduled_for: Optional[str] = None
    done: bool = False
    created_by: str
    created_at: str


def _lead_out(data: dict) -> LeadResponse:
    data = dict(data)
    next_fu = data.get("next_follow_up")
    data["is_overdue"] = False
    if next_fu:
        try:
            d = date.fromisoformat(next_fu[:10])
            data["is_overdue"] = d < date.today()
        except (ValueError, TypeError):
            pass
    return LeadResponse(**data)


@router.get("/leads", response_model=List[LeadResponse])
async def list_leads(
    status: Optional[str] = None,
    owner: Optional[str] = None,
    priority: Optional[str] = None,
    _: None = Depends(require_permission("bd", "view"))
):
    """List BD leads, optional status/owner/priority filters."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("bdLeads").where("tenant_id", "==", tenant_id).stream())
    out = []
    for d in docs:
        data = d.to_dict()
        if data.get("is_active") is False:
            continue
        data["id"] = d.id
        if status and data.get("status") != status:
            continue
        if owner and data.get("owner") != owner:
            continue
        if priority and data.get("priority") != priority:
            continue
        out.append(_lead_out(data))
    out.sort(key=lambda x: (x.is_overdue, date.fromisoformat(x.next_follow_up[:10]) if x.next_follow_up else date.max))
    return out


@router.get("/leads/summary")
async def leads_summary(
    _: None = Depends(require_permission("bd", "view"))
):
    """Pipeline summary — count by status, won value, upcoming follow-ups."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("bdLeads").where("tenant_id", "==", tenant_id).stream())

    by_status = {s: 0 for s in LEAD_STATUSES}
    won_value = 0.0
    total_pipeline = 0.0
    upcoming = []
    today = date.today()
    for d in docs:
        data = d.to_dict()
        if data.get("is_active") is False:
            continue
        status = data.get("status", "New")
        by_status[status] = by_status.get(status, 0) + 1
        val = data.get("estimated_value") or 0
        if status == "Won":
            won_value += val
        if status not in ("Won", "Lost"):
            total_pipeline += val
        nf = data.get("next_follow_up")
        if status not in ("Won", "Lost") and nf:
            due = date.fromisoformat(nf[:10])
            upcoming.append({
                "id": d.id,
                "company_name": data.get("company_name"),
                "due_date": nf,
                "days_left": (due - today).days,
            })

    upcoming = [u for u in upcoming if u["days_left"] <= 7]
    upcoming.sort(key=lambda x: x["days_left"])
    return {
        "by_status": by_status,
        "total": sum(by_status.values()),
        "won_value": round(won_value, 2),
        "pipeline_value": round(total_pipeline, 2),
        "upcoming": upcoming[:20],
    }


@router.post("/leads", response_model=LeadResponse, status_code=201)
async def create_lead(
    body: LeadCreate,
    _: None = Depends(require_permission("bd", "create"))
):
    db = get_db()
    tenant_id = get_current_tenant()
    lead_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": lead_id,
        "tenant_id": tenant_id,
        **body.dict(exclude_none=True),
        "created_at": now,
        "updated_at": None,
    }
    db.collection("bdLeads").document(lead_id).set(doc)
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="CREATE", entity="bd", entity_id=lead_id, diff={"company": body.company_name})
    return _lead_out(doc)


@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    _: None = Depends(require_permission("bd", "view"))
):
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("bdLeads").document(lead_id).get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    data = dict(doc.to_dict())
    data["id"] = doc.id
    return _lead_out(data)


@router.patch("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    _: None = Depends(require_permission("bd", "update"))
):
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("bdLeads").document(lead_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc_ref.update(update_data)
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="UPDATE", entity="bd", entity_id=lead_id)
    data = doc.to_dict() | update_data
    data["id"] = lead_id
    return _lead_out(data)


@router.delete("/leads/{lead_id}")
async def delete_lead(
    lead_id: str,
    _: None = Depends(require_permission("bd", "delete"))
):
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("bdLeads").document(lead_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    doc_ref.update({"is_active": False, "deleted_at": datetime.now(timezone.utc).isoformat()})
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="DELETE", entity="bd", entity_id=lead_id)
    return {"message": "Lead deleted"}


@router.get("/leads/{lead_id}/followups", response_model=List[FollowUpResponse])
async def list_followups(
    lead_id: str,
    _: None = Depends(require_permission("bd", "view"))
):
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("bdLeads").document(lead_id).get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    docs = list(db.collection("bdFollowups").where("tenant_id", "==", tenant_id).where("lead_id", "==", lead_id).stream())
    out = [FollowUpResponse(id=d.id, **d.to_dict()) for d in docs]
    out.sort(key=lambda x: x.created_at, reverse=True)
    return out


@router.post("/leads/{lead_id}/followups", response_model=FollowUpResponse, status_code=201)
async def create_followup(
    lead_id: str,
    body: FollowUpCreate,
    _: None = Depends(require_permission("bd", "create"))
):
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("bdLeads").document(lead_id).get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    fup_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    fup = {
        "id": fup_id,
        "lead_id": lead_id,
        "tenant_id": tenant_id,
        "type": body.type,
        "summary": body.summary,
        "scheduled_for": body.scheduled_for,
        "done": False,
        "created_by": "system",
        "created_at": now,
    }
    db.collection("bdFollowups").document(fup_id).set(fup)
    return FollowUpResponse(**fup)