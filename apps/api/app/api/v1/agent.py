from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import json
import base64
import hashlib

router = APIRouter()

# ── Models ───────────────────────────────────────────────────────
class AgentQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query or task")
    user_id: str
    tenant_id: str
    session_id: Optional[str] = None

class AgentQueryResponse(BaseModel):
    response: str
    gql: str  # Generated Firestore GQL or action description
    confidence: float
    suggested_actions: list

class AgentExecutionRequest(BaseModel):
    workflow_id: str
    parameters: dict
    tenant_id: str

class AgentExecutionResponse(BaseModel):
    status: str
    result: Optional[dict]
    error: Optional[str]
    logs: list

# ── In-memory “agent state” (replace with DB/service in prod) ────
_agent_state = {}

# ── Natural Language → Firestore GQL mapper (toy implementation) ────
ENITIES = {
    "clients": {"pk": "id", "fields": {"tenant_id": "string", "name": "string", "pan": "string", "gstin": "string"}},
    "tasks": {"pk": "id", "fields": {"tenant_id": "string", "type": "string", "priority": "string", "status": "string", "due_date": "string", "client_id": "string", "assignee_id": "string"}},
    "documents": {"pk": "id", "fields": {"tenant_id": "string", "client_id": "string", "folder_id": "string", "name": "string", "gcs_path": "string"}},
    "invoices": {"pk": "id", "fields": {"tenant_id": "string", "client_id": "string", "invoice_number": "string", "total": "number", "status": "string"}},
}

def nlq_to_gql(query: str, tenant_id: str) -> str:
    """Very naive NLQ → GQL mapper for demo purposes."""
    q = query.lower()
    results = []
    if "overdue" in q and "task" in q:
        results.append(f"WHERE tenant_id == '{tenant_id}' AND status == 'Overdue'")
    if "client" in q and "pan" in q:
        results.append(f"WHERE tenant_id == '{tenant_id}' AND pan == '")
    if "compliance" in q:
        results.append(f"WHERE tenant_id == '{tenant_id}'")
    if not results:
        results.append("WHERE tenant_id == '{tenant_id}'")
    return " OR ".join(results)

# ── API Endpoints ───────────────────────────────────────────────

@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(request: AgentQueryRequest):
    """Natural language → GQL + Firestore query."""
    try:
        gql = nlq_to_gql(request.query, request.tenant_id)
        # In a real system, an LLM would parse the query and return a GQL string.
        # Here we just return a placeholder.
        return {
            "response": f"Processed query: '{request.query}' for tenant {request.tenant_id}",
            "gql": gql,
            "confidence": 0.85,
            "suggested_actions": ["view_tasks", "create_task", "export_data"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute", response_model=AgentExecutionResponse)
async def agent_execute(request: AgentExecutionRequest):
    """Kick‑off a workflow (n8n, step‑function, etc.) and return status."""
    # Placeholder: just echo back the request with a generated execution ID
    execution_id = f"exec-{os.urandom(4).hex()}"
    _agent_state[execution_id] = {
        "workflow_id": request.workflow_id,
        "parameters": request.parameters,
        "tenant_id": request.tenant_id,
        "status": "pending",
        "logs": [],
    }
    return {
        "status": "pending",
        "result": None,
        "error": None,
        "logs": [f"Execution {execution_id} started"],
    }

@router.get("/health")
async def agent_health():
    return {"status": "ok", "service": "agent", "version": "0.2.0"}

