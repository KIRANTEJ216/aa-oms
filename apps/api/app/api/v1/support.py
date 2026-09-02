from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field, validator
from app.schemas.common import FirestoreOut
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission
from app.core.rate_limit import limiter, RATE_LIMITS

router = APIRouter()

SUPPORT_CATEGORIES = ["Technical", "Billing", "General", "Feature Request", "Bug Report"]
SUPPORT_PRIORITIES = ["Low", "Medium", "High", "Urgent"]
SUPPORT_STATUSES = ["Open", "In Progress", "Waiting on Customer", "Resolved", "Closed"]


class SupportTicketCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    category: str = Field("General", description="Technical/Billing/General/Feature Request/Bug Report")
    priority: str = Field("Medium", description="Low/Medium/High/Urgent")
    client_id: Optional[str] = None

    @validator('category')
    def validate_category(cls, v):
        if v not in SUPPORT_CATEGORIES:
            raise ValueError(f"category must be one of {SUPPORT_CATEGORIES}")
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v not in SUPPORT_PRIORITIES:
            raise ValueError(f"priority must be one of {SUPPORT_PRIORITIES}")
        return v


class SupportTicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None

    @validator('category')
    def validate_category(cls, v):
        if v and v not in SUPPORT_CATEGORIES:
            raise ValueError(f"category must be one of {SUPPORT_CATEGORIES}")
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v and v not in SUPPORT_PRIORITIES:
            raise ValueError(f"priority must be one of {SUPPORT_PRIORITIES}")
        return v

    @validator('status')
    def validate_status(cls, v):
        if v and v not in SUPPORT_STATUSES:
            raise ValueError(f"status must be one of {SUPPORT_STATUSES}")
        return v


class SupportTicketResponse(FirestoreOut):
    id: str
    tenant_id: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    client_id: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    source: str = "web"  # web, chatbot, email, api


class ChatbotMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    context: Optional[dict] = None


class ChatbotResponse(BaseModel):
    response: str
    session_id: str
    ticket_created: bool = False
    ticket_id: Optional[str] = None
    suggested_actions: List[str] = []


async def trigger_n8n_webhook(event: str, payload: dict) -> bool:
    """Trigger n8n webhook for automation (Google Sheets, Slack, etc.)"""
    import httpx
    from app.core.config import get_settings
    
    settings = get_settings()
    webhook_url = getattr(settings, 'n8n_webhook_url', None)
    
    if not webhook_url:
        return False
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(webhook_url, json={
                "event": event,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": payload
            })
        return True
    except Exception:
        return False


@router.get("/", response_model=List[SupportTicketResponse])
async def list_support_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    _: None = Depends(require_permission("support", "view"))
):
    """List support tickets for the current tenant."""
    db = get_db()
    tenant_id = get_current_tenant()

    query = db.collection("support_tickets").where("tenant_id", "==", tenant_id)
    docs = list(query.stream())
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        if status and data.get("status") != status:
            continue
        if category and data.get("category") != category:
            continue
        if priority and data.get("priority") != priority:
            continue
        results.append(SupportTicketResponse(**data))
    return results


@router.post("/", response_model=SupportTicketResponse, status_code=201)
async def create_support_ticket(
    ticket: SupportTicketCreate,
    request: Request,
    _: None = Depends(require_permission("support", "create"))
):
    """Create a new support ticket."""
    db = get_db()
    tenant_id = get_current_tenant()

    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Get user from auth header
    created_by = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from app.core.security import decode_token
            token = auth_header[7:]
            payload = decode_token(token)
            created_by = payload.get("sub")
        except Exception:
            pass

    ticket_doc = {
        "id": ticket_id,
        "tenant_id": tenant_id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": "Open",
        "client_id": ticket.client_id,
        "assigned_to": None,
        "resolution": None,
        "created_at": now,
        "updated_at": None,
        "created_by": created_by,
        "source": "web",
    }

    db.collection("support_tickets").document(ticket_id).set(ticket_doc)

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id=created_by or "system", action="CREATE", entity="support_tickets", entity_id=ticket_id)

    # Trigger n8n webhook for automation
    await trigger_n8n_webhook("support_ticket.created", {
        "ticket_id": ticket_id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": "Open",
        "tenant_id": tenant_id,
        "created_by": created_by,
    })

    return SupportTicketResponse(**ticket_doc)


@router.get("/{ticket_id}", response_model=SupportTicketResponse)
async def get_support_ticket(
    ticket_id: str,
    _: None = Depends(require_permission("support", "view"))
):
    """Get a single support ticket by ID."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("support_tickets").document(ticket_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    data = doc.to_dict()
    data["id"] = doc.id
    return SupportTicketResponse(**data)


@router.patch("/{ticket_id}", response_model=SupportTicketResponse)
async def update_support_ticket(
    ticket_id: str,
    ticket_update: SupportTicketUpdate,
    _: None = Depends(require_permission("support", "update"))
):
    """Partial update of a support ticket."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("support_tickets").document(ticket_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")

    update_data = {k: v for k, v in ticket_update.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    # If status changed to Resolved/Closed, add resolution timestamp
    if "status" in update_data and update_data["status"] in ["Resolved", "Closed"]:
        update_data["resolved_at"] = datetime.now(timezone.utc).isoformat()

    db.collection("support_tickets").document(ticket_id).update(update_data)

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="UPDATE", entity="support_tickets", entity_id=ticket_id)

    # Trigger n8n webhook for status changes
    if "status" in update_data:
        await trigger_n8n_webhook("support_ticket.status_changed", {
            "ticket_id": ticket_id,
            "new_status": update_data["status"],
            "tenant_id": tenant_id,
        })

    doc = db.collection("support_tickets").document(ticket_id).get()
    data = doc.to_dict()
    data["id"] = doc.id
    return SupportTicketResponse(**data)


@router.delete("/{ticket_id}")
async def delete_support_ticket(
    ticket_id: str,
    _: None = Depends(require_permission("support", "delete"))
):
    """Delete a support ticket."""
    db = get_db()
    tenant_id = get_current_tenant()
    doc = db.collection("support_tickets").document(ticket_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")

    db.collection("support_tickets").document(ticket_id).update({
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "is_active": False,
    })

    from app.core.audit import log_audit
    await log_audit(tenant_id=tenant_id, actor_id="system", action="DELETE", entity="support_tickets", entity_id=ticket_id)
    return {"message": "Support ticket deleted"}


@router.post("/chatbot", response_model=ChatbotResponse)
@limiter.limit(RATE_LIMITS["support_chatbot"])
async def chatbot_interaction(
    message: ChatbotMessage,
    request: Request,
):
    """Chatbot endpoint for support ticket creation via conversational AI."""
    import httpx
    from app.core.config import get_settings
    
    settings = get_settings()
    db = get_db()
    tenant_id = get_current_tenant()
    
    # Generate session ID if not provided
    session_id = message.session_id or str(uuid.uuid4())
    
    # Simple keyword-based intent detection (can be replaced with LLM)
    user_message = message.message.lower()
    
    # Check if user wants to create a ticket
    create_keywords = ["create ticket", "log issue", "report bug", "support request", "help with", "problem with", "issue with"]
    wants_ticket = any(keyword in user_message for keyword in create_keywords)
    
    # Determine category from message
    category = "General"
    if any(kw in user_message for kw in ["bug", "error", "crash", "broken", "not working"]):
        category = "Bug Report"
    elif any(kw in user_message for kw in ["bill", "invoice", "payment", "charge", "refund"]):
        category = "Billing"
    elif any(kw in user_message for kw in ["feature", "request", "add", "enhancement", "improvement"]):
        category = "Feature Request"
    elif any(kw in user_message for kw in ["technical", "api", "integration", "login", "password"]):
        category = "Technical"
    
    # Determine priority
    priority = "Medium"
    if any(kw in user_message for kw in ["urgent", "critical", "emergency", "down", "outage"]):
        priority = "Urgent"
    elif any(kw in user_message for kw in ["high priority", "important", "asap"]):
        priority = "High"
    elif any(kw in user_message for kw in ["low priority", "whenever", "minor"]):
        priority = "Low"
    
    ticket_created = False
    ticket_id = None
    response_text = ""
    suggested_actions = []
    
    if wants_ticket:
        # Create support ticket
        ticket_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Get user from auth header
        created_by = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.core.security import decode_token
                token = auth_header[7:]
                payload = decode_token(token)
                created_by = payload.get("sub")
            except Exception:
                pass
        
        ticket_doc = {
            "id": ticket_id,
            "tenant_id": tenant_id,
            "title": message.message[:100] + ("..." if len(message.message) > 100 else ""),
            "description": message.message,
            "category": category,
            "priority": priority,
            "status": "Open",
            "client_id": None,
            "assigned_to": None,
            "resolution": None,
            "created_at": now,
            "updated_at": None,
            "created_by": created_by,
            "source": "chatbot",
            "chatbot_session_id": session_id,
        }
        
        db.collection("support_tickets").document(ticket_id).set(ticket_doc)
        
        from app.core.audit import log_audit
        await log_audit(tenant_id=tenant_id, actor_id=created_by or "system", action="CREATE", entity="support_tickets", entity_id=ticket_id)
        
        # Trigger n8n webhook
        await trigger_n8n_webhook("support_ticket.created", {
            "ticket_id": ticket_id,
            "title": ticket_doc["title"],
            "description": message.message,
            "category": category,
            "priority": priority,
            "status": "Open",
            "tenant_id": tenant_id,
            "created_by": created_by,
            "source": "chatbot",
        })
        
        ticket_created = True
        response_text = f"I've created a support ticket for you (ID: {ticket_id[:8]}...). Category: {category}, Priority: {priority}. Our team will review it shortly."
        suggested_actions = ["View ticket status", "Add more details", "Contact support directly"]
    else:
        # Provide helpful response based on message content
        if any(kw in user_message for kw in ["hello", "hi", "hey", "start"]):
            response_text = "Hello! I'm your support assistant. How can I help you today? You can report issues, ask questions, or request features."
            suggested_actions = ["Report a bug", "Ask about billing", "Request a feature", "Technical help"]
        elif any(kw in user_message for kw in ["status", "check ticket", "my ticket"]):
            response_text = "To check your ticket status, please provide the ticket ID or visit the Support Tickets page in the dashboard."
            suggested_actions = ["View my tickets", "Create new ticket"]
        elif any(kw in user_message for kw in ["thanks", "thank you", "bye"]):
            response_text = "You're welcome! Feel free to reach out if you need any further assistance. Have a great day!"
            suggested_actions = ["Create new ticket", "View my tickets"]
        else:
            response_text = "I understand you need help. Could you please describe the issue in more detail? I can create a support ticket for you."
            suggested_actions = ["Create support ticket", "Browse help articles", "Contact support"]
    
    return ChatbotResponse(
        response=response_text,
        session_id=session_id,
        ticket_created=ticket_created,
        ticket_id=ticket_id,
        suggested_actions=suggested_actions
    )


@router.get("/stats/summary")
async def support_ticket_stats(
    _: None = Depends(require_permission("support", "view"))
):
    """Aggregate counts for the dashboard."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("support_tickets").where("tenant_id", "==", tenant_id).stream())

    by_status = {s: 0 for s in SUPPORT_STATUSES}
    by_category = {c: 0 for c in SUPPORT_CATEGORIES}
    by_priority = {p: 0 for p in SUPPORT_PRIORITIES}
    by_source = {"web": 0, "chatbot": 0, "email": 0, "api": 0}

    for doc in docs:
        data = doc.to_dict()
        status = data.get("status", "Open")
        category = data.get("category", "General")
        priority = data.get("priority", "Medium")
        source = data.get("source", "web")
        
        by_status[status] = by_status.get(status, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
        by_priority[priority] = by_priority.get(priority, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1

    return {
        "total": len(docs),
        "by_status": by_status,
        "by_category": by_category,
        "by_priority": by_priority,
        "by_source": by_source,
    }