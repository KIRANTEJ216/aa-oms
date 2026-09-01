from fastapi import APIRouter, Depends, HTTPException
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission
from app.infra.secrets.client import encrypt_value, decrypt_value

router = APIRouter()

# ── Schemas ──────────────────────────────────────────────────────
class InvoiceItem(BaseModel):
    description: str = Field(..., min_length=1)
    sac_code: str = Field(..., description="6-digit Service Accounting Code, e.g. 998299")
    amount: float = Field(..., gt=0)
    gst_rate: float = Field(18, ge=0, le=28)  # default 18% for professional services

class InvoiceCreate(BaseModel):
    client_id: str
    invoice_type: str = Field("Tax Invoice", pattern="^(Tax Invoice|Proforma Invoice|Credit Note|Debit Note|Receipt)$")
    items: List[InvoiceItem]
    due_days: int = Field(30, ge=1, le=365)  # days until due
    gst_treatment: str = Field("IGST", pattern="^(IGST|CGST_SGST)$")  # auto-detect from client GST state vs firm GST state

class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    client_id: str
    invoice_type: str
    gst_treatment: str  # IGST or CGST_SGST
    gst_breakup: dict  # {"cgst": float, "sgst": float, "igst": float} or {"igst": float}
    total: float
    due_date: str
    status: str  # Unpaid | Partially Paid | Paid | Overdue
    created_at: str

class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    payment_method: str = Field("UPI", pattern="^(UPI|Bank Transfer|Cheque|Cash)$")

class PaymentResponse(BaseModel):
    id: str
    invoice_id: str
    amount: float
    payment_method: str
    payment_date: str
    status: str  # success | pending | failed

# ── Helper functions ─────────────────────────────────────────────
def _compute_gst_breakup(items: List[InvoiceItem], gst_treatment: str) -> dict:
    """Compute GST breakup: either CGST+SGST (intra-state) or IGST (inter-state)."""
    total_gst = sum(item.amount * item.gst_rate / 100 for item in items)
    if gst_treatment == "CGST_SGST":
        # Split equally (or as configured) — here we split 50/50
        cgst = total_gst / 2
        sgst = total_gst / 2
        return {"cgst": round(cgst, 2), "sgst": round(sgst, 2), "igst": 0}
    else:  # IGST
        return {"igst": round(total_gst, 2), "cgst": 0, "sgst": 0}

def _compute_invoice_number(client_id: str, current_date: str) -> str:
    """Generate INV-FY-XXXX invoice number."""
    # Simple counter based on number of invoices for this client + current FY
    from datetime import datetime
    fy = current_date[:4]  # first 4 chars = fiscal year start
    # We'll just use a simple incrementing counter stored in a doc
    return f"INV-{fy}-{1001}"  # placeholder — in prod this would be dynamic

def _compute_due_date(due_days: int) -> str:
    from datetime import datetime, timedelta
    return (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d")

# ── Routes ───────────────────────────────────────────────────────

@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    invoice: InvoiceCreate,
    _: None = Depends(require_permission("invoices", "create"))
):
    """Create a new invoice with GST breakup."""
    db = get_db()
    tenant_id = get_current_tenant()
    
    # Verify client exists in tenant
    client_doc = db.collection("clients").document(invoice.client_id).get()
    if not client_doc.exists or client_doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Compute invoice number and due date
    invoice_number = _compute_invoice_number(invoice.client_id, datetime.now(timezone.utc).isoformat())
    due_date = _compute_due_date(invoice.due_days)
    
    # Compute GST breakup
    gst_breakup = _compute_gst_breakup(invoice.items, invoice.gst_treatment)
    
    # Build invoice document
    invoice_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    invoice_doc = {
        "id": invoice_id,
        "tenant_id": tenant_id,
        "client_id": invoice.client_id,
        "invoice_number": invoice_number,
        "invoice_type": invoice.invoice_type,
        "gst_treatment": invoice.gst_treatment,
        "gst_breakup": gst_breakup,
        "items": [{"description": i.description, "sac_code": i.sac_code, "amount": i.amount, "gst_rate": i.gst_rate} for i in invoice.items],
        "total": sum(item.amount for item in invoice.items) + sum(gst_breakup.values()),
        "due_date": due_date,
        "status": "Unpaid",
        "created_at": now,
    }
    
    db.collection("invoices").document(invoice_id).set(invoice_doc)
    
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="CREATE", entity="invoices", entity_id=invoice_id)
    
    return InvoiceResponse(
        id=invoice_id,
        invoice_number=invoice_number,
        client_id=invoice.client_id,
        invoice_type=invoice.invoice_type,
        gst_treatment=invoice.gst_treatment,
        gst_breakup=gst_breakup,
        total=invoice_doc["total"],
        due_date=due_date,
        status="Unpaid",
        created_at=now,
    )

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    _: None = Depends(require_permission("invoices", "view"))
):
    """List invoices with optional filters."""
    db = get_db()
    tenant_id = get_current_tenant()
    
    query = db.collection("invoices").where("tenant_id", "==", tenant_id)
    if client_id:
        query = query.where("client_id", "==", client_id)
    
    docs = list(query.stream())
    results = []
    for d in docs:
        data = d.to_dict()
        if status and data.get("status") != status:
            continue
        results.append(InvoiceResponse(
            id=d.id,
            invoice_number=data["invoice_number"],
            client_id=data["client_id"],
            invoice_type=data["invoice_type"],
            gst_treatment=data["gst_treatment"],
            gst_breakup=data["gst_breakup"],
            total=data["total"],
            due_date=data["due_date"],
            status=data["status"],
            created_at=data["created_at"],
        ))
    return results

@router.get("/invoices/aging")
async def aging_buckets(
    _: None = Depends(require_permission("invoices", "view"))
):
    """Return aging buckets: 0-30, 31-60, 61-90, 90+ days."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("invoices").where("tenant_id", "==", tenant_id).stream())
    
    buckets = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    today = datetime.now().date()
    
    for d in docs:
        data = d.to_dict()
        due = datetime.strptime(data["due_date"], "%Y-%m-%d").date()
        delta = (today - due).days
        if delta <= 0:
            continue
        elif delta <= 30:
            buckets["0-30"] += 1
        elif delta <= 60:
            buckets["31-60"] += 1
        elif delta <= 90:
            buckets["61-90"] += 1
        else:
            buckets["90+"] += 1
    
    return {"buckets": buckets, "total": sum(buckets.values())}

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    _: None = Depends(require_permission("invoices", "view"))
):
    """Get a single invoice."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("invoices").document(invoice_id).get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    data = doc.to_dict()
    return InvoiceResponse(
        id=doc.id,
        invoice_number=data["invoice_number"],
        client_id=data["client_id"],
        invoice_type=data["invoice_type"],
        gst_treatment=data["gst_treatment"],
        gst_breakup=data["gst_breakup"],
        total=data["total"],
        due_date=data["due_date"],
        status=data["status"],
        created_at=data["created_at"],
    )

@router.post("/invoices/{invoice_id}/payments", response_model=PaymentResponse)
async def record_payment(
    invoice_id: str,
    payment: PaymentCreate,
    _: None = Depends(require_permission("invoices", "update"))
):
    """Record a payment against an invoice."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc_ref = db.collection("invoices").document(invoice_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    data = doc.to_dict()
    new_total = data["total"] - payment.amount
    new_status = "Paid" if new_total <= 0 else ("Partially Paid" if new_total > 0 and data["status"] != "Overdue" else "Overdue")
    
    doc_ref.update({
        "total": new_total,
        "status": new_status,
        "last_payment_date": datetime.now(timezone.utc).isoformat(),
    })
    
    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="PAYMENT", entity="invoices", entity_id=invoice_id, diff={"amount": payment.amount, "new_total": new_total, "new_status": new_status})
    
    return PaymentResponse(
        id=str(uuid.uuid4()),
        invoice_id=invoice_id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        payment_date=datetime.now(timezone.utc).isoformat(),
        status="success",
    )


