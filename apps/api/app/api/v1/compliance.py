from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime, timezone, date
import uuid
from pydantic import BaseModel, Field, validator
from app.schemas.common import FirestoreOut
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission
from app.core.security import decode_token

router = APIRouter()

# ── Health computation helpers ────────────────────────────────────
def _status_for_due_date(actual_due: date) -> str:
    """Green: >7d away, Amber: ≤7d, Red: overdue (past)."""
    today = date.today()
    if actual_due < today:
        return "Red"
    if (actual_due - today).days <= 7:
        return "Amber"
    return "Green"


# ── Schemas ────────────────────────────────────────────────────────
COMPLIANCE_CODES = [
    "GSTR1", "GSTR3B", "GSTR9",
    "ITR_NON_AUDIT", "ITR_AUDIT",
    "TDS_26Q", "ADV_TAX",
    "ROC_MGT7", "ROC_AOC4",
]
COMPLIANCE_FREQUENCIES = ["Monthly", "Quarterly", "Annually", "One-time"]

# Step-by-step filing checklists (doc §7 workflows) — one checklist per compliance code.
FILING_CHECKLISTS: dict[str, dict] = {
    "GSTR1": {
        "code": "GSTR1",
        "name": "GSTR-1 (Outbound invoices)",
        "frequency": "Monthly",
        "due_rule": "11th of following month",
        "items": [
            "Verify all sales invoices recorded in books",
            "Reconcile with GSTR-2B/2A",
            "Check HSN-wise summary totals",
            "Export JSON from accounting software",
            "File on GST portal before deadline",
            "Download acknowledgement",
        ],
    },
    "GSTR3B": {
        "code": "GSTR3B",
        "name": "GSTR-3B (Summary return + tax payment)",
        "frequency": "Monthly",
        "due_rule": "20th of following month",
        "items": [
            "Reconcile with GSTR-1 filed",
            "Compute tax liability (IGST/CGST/SGST)",
            "Set off eligible ITC",
            "Pay balance via GST challan",
            "File GSTR-3B with payment confirmation",
            "Download acknowledgement",
        ],
    },
    "GSTR9": {
        "code": "GSTR9",
        "name": "GSTR-9 (Annual return)",
        "frequency": "Annually",
        "due_rule": "31st December of following FY",
        "items": [
            "Reconcile books with GSTR-1 and 3B",
            "Verify turnover declared matches audited figures",
            "Check tax paid vs liability",
            "Disclose any additional tax demands",
            "File on GST portal",
        ],
    },
    "ITR_NON_AUDIT": {
        "code": "ITR_NON_AUDIT",
        "name": "ITR Individual/HUF (non-audit)",
        "frequency": "Annually",
        "due_rule": "31st July",
        "items": [
            "Collect Form 16 / TDS certificates",
            "Compute total income",
            "Verify capital gains statements from broker",
            "Check 26AS / AIS",
            "File ITR-1 / ITR-2 via income tax portal",
            "Verify ITR-V acknowledgement",
        ],
    },
    "ITR_AUDIT": {
        "code": "ITR_AUDIT",
        "name": "ITR Company/Audit Cases",
        "frequency": "Annually",
        "due_rule": "31st October",
        "items": [
            "Complete tax audit (Form 3CA/3CB + 3CD)",
            "Compute book profit u/s 115JB",
            "Reconcile MAT vs regular tax",
            "File ITR-3/ITR-6",
            "E-verify via DSC or EVC",
        ],
    },
    "TDS_26Q": {
        "code": "TDS_26Q",
        "name": "TDS Return 26Q/24Q",
        "frequency": "Quarterly",
        "due_rule": "31st of month following quarter",
        "items": [
            "Reconcile TDS deposited with challans",
            "Verify TAN and deductee PANs",
            "Check TDS rates applied correctly",
            "Prepare 26Q/24Q statement",
            "File on TRACES portal",
        ],
    },
    "ADV_TAX": {
        "code": "ADV_TAX",
        "name": "Advance Tax Instalment",
        "frequency": "Quarterly",
        "due_rule": "15th Jun (15%), 15th Sep (45%), 15th Dec (75%), 15th Mar (100%)",
        "items": [
            "Estimate current year income",
            "Compute tax liability",
            "Calculate instalment due (cumulative %)",
            "Pay via challan 280",
            "Record in books and 26Q",
        ],
    },
    "ROC_MGT7": {
        "code": "ROC_MGT7",
        "name": "ROC Annual Return MGT-7",
        "frequency": "Annually",
        "due_rule": "60 days from AGM date",
        "items": [
            "Update register of members",
            "Compile shareholding pattern",
            "Verify board composition",
            "File MGT-7 on MCA portal",
            "Pay filing fee",
        ],
    },
    "ROC_AOC4": {
        "code": "ROC_AOC4",
        "name": "Financial Statements AOC-4",
        "frequency": "Annually",
        "due_rule": "30 days from AGM",
        "items": [
            "Finalize audited financials",
            "Attach director's report",
            "Attach auditor's report",
            "File AOC-4 on MCA portal",
        ],
    },
}


def _checklist_progress_counts(compliance_code: str, progress: Optional[dict]) -> tuple:
    """Return (done, total) for a filing's checklist progress."""
    items = FILING_CHECKLISTS.get(compliance_code, {}).get("items", [])
    total = len(items)
    if not progress:
        return 0, total
    done = sum(1 for i in range(total) if progress.get(str(i)) is True)
    return done, total


class ComplianceFilingUpdate(BaseModel):
    status: Optional[str] = Field(None, description="Filed/Pending/Overdue")
    filed_at: Optional[str] = None
    acknowledgement_ref: Optional[str] = None
    notes: Optional[str] = None
    checklist_progress: Optional[dict] = Field(None, description="{'0': true, '1': false, ...} step completion")

class ComplianceFilingCreate(BaseModel):
    client_id: str
    compliance_code: str
    period: str = Field(..., description="e.g. '2024-25' or 'Q1 FY2024-25'")
    actual_due_date: str = Field(..., description="YYYY-MM-DD")
    notes: Optional[str] = None

    @validator('compliance_code')
    def validate_code(cls, v):
        if v not in COMPLIANCE_CODES:
            raise ValueError(f"compliance_code must be one of {COMPLIANCE_CODES}")
        return v

    @validator('actual_due_date')
    def validate_date(cls, v):
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError('actual_due_date must be ISO format YYYY-MM-DD')
        return v

class ComplianceFilingResponse(FirestoreOut):
    id: str
    tenant_id: str
    client_id: str
    client_name: Optional[str] = None
    compliance_code: str
    compliance_name: Optional[str] = None
    period: str
    actual_due_date: str
    status: str  # Filed / Pending
    health: str  # Green / Amber / Red
    filed_at: Optional[str] = None
    acknowledgement_ref: Optional[str] = None
    notes: Optional[str] = None
    checklist_progress: Optional[dict] = None
    checklist_done: Optional[int] = None
    checklist_total: Optional[int] = None
    created_at: str
    updated_at: Optional[str] = None


def _filing_out(data: dict) -> ComplianceFilingResponse:
    """Build a compliance filing response with health + checklist progress computed on read."""
    data = dict(data)
    try:
        due = date.fromisoformat(data.get("actual_due_date", ""))
        data["health"] = _status_for_due_date(due)
    except (ValueError, TypeError):
        data["health"] = "Green"
    done, total = _checklist_progress_counts(data.get("compliance_code", ""), data.get("checklist_progress"))
    data["checklist_done"] = done
    data["checklist_total"] = total
    return ComplianceFilingResponse(**data)


# ── Routes ────────────────────────────────────────────────────────

@router.get("/types")
async def list_compliance_types(
    _: None = Depends(require_permission("compliance", "view"))
):
    """List all compliance types (global seed)."""
    db = get_db()
    docs = list(db.collection("complianceTypes").stream())
    return [{"code": d.id, **d.to_dict()} for d in docs]


@router.get("/calendar", response_model=List[ComplianceFilingResponse])
async def compliance_calendar(
    period: Optional[str] = None,
    health: Optional[str] = None,  # Green/Amber/Red
    _: None = Depends(require_permission("compliance", "view"))
):
    """List compliance filings, with optional period and health filters. Computes health on read."""
    db = get_db()
    tenant_id = get_current_tenant()

    docs = list(db.collection("complianceFilings").where("tenant_id", "==", tenant_id).stream())

    # Build client name lookup
    client_docs = list(db.collection("clients").where("tenant_id", "==", tenant_id).stream())
    client_map = {d.id: d.to_dict().get("name", "Unknown") for d in client_docs}

    # Build compliance name lookup
    type_docs = list(db.collection("complianceTypes").stream())
    type_map = {d.id: d.to_dict().get("name", d.id) for d in type_docs}

    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        try:
            due = date.fromisoformat(data.get("actual_due_date", ""))
            data["health"] = _status_for_due_date(due)
        except (ValueError, TypeError):
            data["health"] = "Green"
        data["client_name"] = client_map.get(data.get("client_id", ""), "Unknown")
        data["compliance_name"] = type_map.get(data.get("compliance_code", ""), data.get("compliance_code", ""))

        if period and data.get("period") != period:
            continue
        if health and data["health"] != health:
            continue
        results.append(_filing_out(data))
    return results


@router.post("/filings", response_model=ComplianceFilingResponse, status_code=201)
async def create_filing(
    body: ComplianceFilingCreate,
    _: None = Depends(require_permission("compliance", "create"))
):
    """Create a new compliance filing for a client/period."""
    db = get_db()
    tenant_id = get_current_tenant()

    # Verify client exists in tenant
    client_doc = db.collection("clients").document(body.client_id).get()
    if not client_doc.exists:
        raise HTTPException(status_code=404, detail="Client not found")
    if client_doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")

    filing_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    filing_doc = {
        "id": filing_id,
        "tenant_id": tenant_id,
        "client_id": body.client_id,
        "compliance_code": body.compliance_code,
        "period": body.period,
        "actual_due_date": body.actual_due_date,
        "status": "Pending",
        "filed_at": None,
        "acknowledgement_ref": None,
        "notes": body.notes,
        "checklist_progress": None,
        "created_at": now,
        "updated_at": None,
    }
    db.collection("complianceFilings").document(filing_id).set(filing_doc)

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="CREATE", entity="complianceFilings", entity_id=filing_id)

    return _filing_out(filing_doc)


@router.patch("/filings/{filing_id}", response_model=ComplianceFilingResponse)
async def update_filing(
    filing_id: str,
    body: ComplianceFilingUpdate,
    _: None = Depends(require_permission("compliance", "update"))
):
    """Update a filing (e.g., mark as Filed, add acknowledgement ref)."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("complianceFilings").document(filing_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Filing not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")

    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    db.collection("complianceFilings").document(filing_id).update(update_data)

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="UPDATE", entity="complianceFilings", entity_id=filing_id)

    doc = db.collection("complianceFilings").document(filing_id).get()
    data = dict(doc.to_dict())
    data["id"] = doc.id
    return _filing_out(data)


@router.get("/health")
async def compliance_health(
    _: None = Depends(require_permission("compliance", "view"))
):
    """Aggregate compliance health (Green/Amber/Red counts) for the tenant."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("complianceFilings").where("tenant_id", "==", tenant_id).stream())

    by_health = {"Green": 0, "Amber": 0, "Red": 0}
    by_code = {}
    today = date.today()
    upcoming = []

    for doc in docs:
        data = doc.to_dict()
        try:
            due = date.fromisoformat(data.get("actual_due_date", ""))
            health = _status_for_due_date(due)
        except (ValueError, TypeError):
            health = "Green"
        by_health[health] = by_health.get(health, 0) + 1
        code = data.get("compliance_code", "Unknown")
        by_code[code] = by_code.get(code, 0) + 1
        if health in ("Amber", "Red") and data.get("status") != "Filed":
            upcoming.append({
                "id": doc.id,
                "compliance_code": code,
                "period": data.get("period"),
                "actual_due_date": data.get("actual_due_date"),
                "health": health,
                "client_id": data.get("client_id"),
                "days_until_due": (due - today).days,
            })

    upcoming.sort(key=lambda x: x.get("days_until_due", 999))
    return {
        "total": len(docs),
        "by_health": by_health,
        "by_code": by_code,
        "upcoming": upcoming[:20],
    }


@router.get("/checklist/{compliance_code}")
async def get_checklist(
    compliance_code: str,
    _: None = Depends(require_permission("compliance", "view"))
):
    """Return a filing checklist for a given compliance code (per PDF p.12-14) — step-by-step guide."""
    if compliance_code not in FILING_CHECKLISTS:
        raise HTTPException(status_code=404, detail=f"Checklist not defined for {compliance_code}")
    return FILING_CHECKLISTS[compliance_code]
