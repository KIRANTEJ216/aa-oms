"""
ABAC (Attribute-Based Access Control) Engine:
- Fine-grained resource-level permissions beyond RBAC
- Policy evaluation with attributes (user, resource, environment, action)
- Support for complex rules: time-based, location-based, ownership, hierarchy
- Integration with existing RBAC system
"""
from fastapi import HTTPException, Request, Depends
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, time, timezone
from app.core.auth import get_current_user
from app.core.tenant import get_current_tenant
from app.infra.firestore.client import get_db
import re


class Effect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class Attribute:
    """Represents an attribute for policy evaluation."""
    name: str
    value: Any
    category: str  # "subject", "resource", "action", "environment"


@dataclass
class PolicyRule:
    """A single policy rule with condition and effect."""
    effect: Effect
    condition: Dict[str, Any]  # Attribute conditions to match
    priority: int = 0
    description: str = ""


@dataclass
class Policy:
    """A collection of rules with combining algorithm."""
    id: str
    name: str
    rules: List[PolicyRule] = field(default_factory=list)
    combining_algorithm: str = "deny_overrides"  # deny_overrides, permit_overrides, first_applicable
    target: Dict[str, Any] = field(default_factory=dict)  # Applicability target
    
    def evaluate(self, attributes: Dict[str, Attribute]) -> Effect:
        """Evaluate policy against attributes."""
        # Check if policy applies to this request
        if not self._matches_target(attributes):
            return Effect.DENY  # Not applicable
        
        # Sort rules by priority
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)
        
        if self.combining_algorithm == "deny_overrides":
            # Any deny wins
            for rule in sorted_rules:
                if self._matches_rule(rule, attributes):
                    if rule.effect == Effect.DENY:
                        return Effect.DENY
            # If no deny, check for permit
            for rule in sorted_rules:
                if self._matches_rule(rule, attributes):
                    if rule.effect == Effect.ALLOW:
                        return Effect.ALLOW
            return Effect.DENY
        
        elif self.combining_algorithm == "permit_overrides":
            # Any permit wins
            for rule in sorted_rules:
                if self._matches_rule(rule, attributes):
                    if rule.effect == Effect.ALLOW:
                        return Effect.ALLOW
            return Effect.DENY
        
        elif self.combining_algorithm == "first_applicable":
            # First matching rule wins
            for rule in sorted_rules:
                if self._matches_rule(rule, attributes):
                    return rule.effect
            return Effect.DENY
        
        return Effect.DENY
    
    def _matches_target(self, attributes: Dict[str, Attribute]) -> bool:
        """Check if policy target matches request."""
        for key, value in self.target.items():
            if key not in attributes:
                return False
            if not self._match_value(attributes[key].value, value):
                return False
        return True
    
    def _matches_rule(self, rule: PolicyRule, attributes: Dict[str, Attribute]) -> bool:
        """Check if rule condition matches attributes."""
        for key, expected in rule.condition.items():
            if key not in attributes:
                return False
            if not self._match_value(attributes[key].value, expected):
                return False
        return True
    
    def _match_value(self, actual: Any, expected: Any) -> bool:
        """Match actual value against expected (supports operators)."""
        if isinstance(expected, dict):
            # Operator-based matching
            for op, val in expected.items():
                if op == "eq":
                    return actual == val
                elif op == "ne":
                    return actual != val
                elif op == "in":
                    return actual in val if isinstance(val, list) else actual == val
                elif op == "not_in":
                    return actual not in val if isinstance(val, list) else actual != val
                elif op == "gt":
                    return actual > val
                elif op == "gte":
                    return actual >= val
                elif op == "lt":
                    return actual < val
                elif op == "lte":
                    return actual <= val
                elif op == "regex":
                    return bool(re.match(val, str(actual)))
                elif op == "contains":
                    return val in actual if hasattr(actual, '__contains__') else False
                elif op == "startswith":
                    return str(actual).startswith(val)
                elif op == "endswith":
                    return str(actual).endswith(val)
            return False
        else:
            # Simple equality
            return actual == expected


class ABACEngine:
    """
    Main ABAC engine for policy evaluation.
    Combines multiple policies and provides authorization decisions.
    """
    
    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        self._load_default_policies()
    
    def _load_default_policies(self):
        """Load default policies for CAOMS."""
        
        # Policy: Resource Ownership
        self.add_policy(Policy(
            id="resource_ownership",
            name="Resource Ownership Access",
            combining_algorithm="permit_overrides",
            target={"category": "resource"},
            rules=[
                PolicyRule(
                    effect=Effect.ALLOW,
                    priority=100,
                    condition={
                        "subject.id": {"eq": "{{resource.owner_id}}"},
                        "action": {"in": ["read", "update", "delete"]}
                    },
                    description="Owners can read/update/delete their resources"
                ),
                PolicyRule(
                    effect=Effect.ALLOW,
                    priority=90,
                    condition={
                        "subject.id": {"eq": "{{resource.assignee_id}}"},
                        "action": {"in": ["read", "update"]}
                    },
                    description="Assignees can read/update assigned resources"
                ),
            ]
        ))
        
        # Policy: Time-Based Access
        self.add_policy(Policy(
            id="time_based_access",
            name="Business Hours Access",
            combining_algorithm="deny_overrides",
            target={},
            rules=[
                PolicyRule(
                    effect=Effect.DENY,
                    priority=100,
                    condition={
                        "environment.current_time": {"not_in": "business_hours"},
                        "subject.role": {"not_in": ["Super Admin", "Firm Admin"]},
                        "action": {"in": ["create", "update", "delete"]}
                    },
                    description="Non-admins cannot modify outside business hours"
                ),
            ]
        ))
        
        # Policy: Client Data Isolation
        self.add_policy(Policy(
            id="client_data_isolation",
            name="Client Data Access",
            combining_algorithm="permit_overrides",
            target={"resource.type": "client"},
            rules=[
                PolicyRule(
                    effect=Effect.ALLOW,
                    priority=100,
                    condition={
                        "subject.role": {"in": ["Super Admin", "Firm Admin", "Partner"]},
                        "action": {"in": ["read", "create", "update", "delete"]}
                    },
                    description="Admins/partners have full client access"
                ),
                PolicyRule(
                    effect=Effect.ALLOW,
                    priority=90,
                    condition={
                        "subject.id": {"eq": "{{resource.engagement_manager_id}}"},
                        "action": {"in": ["read", "update"]}
                    },
                    description="Engagement managers can access their clients"
                ),
                PolicyRule(
                    effect=Effect.ALLOW,
                    priority=80,
                    condition={
                        "subject.id": {"eq": "{{resource.created_by}}"},
                        "action": {"in": ["read"]}
                    },
                    description="Creators can read their client records"
                ),
            ]
        ))
        
        # Policy: Document Sensitivity
        self.add_policy(Policy(
            id="document_sensitivity",
            name="Document Access by Sensitivity",
            combining_algorithm="deny_overrides",
            target={"resource.type": "document"},
            rules=[
                PolicyRule(
                    effect=Effect.DENY,
                    priority=100,
                    condition={
                        "resource.sensitivity": "high",
                        "subject.role": {"not_in": ["Super Admin", "Firm Admin", "Partner"]},
                        "action": {"in": ["read", "download"]}
                    },
                    description="High sensitivity docs restricted to senior roles"
                ),
                PolicyRule(
                    effect=Effect.DENY,
                    priority=90,
                    condition={
                        "resource.sensitivity": "confidential",
                        "subject.role": "Client",
                        "action": {"in": ["read", "download"]}
                    },
                    description="Clients cannot access confidential docs"
                ),
            ]
        ))
        
        # Policy: Invoice Amount Threshold
        self.add_policy(Policy(
            id="invoice_amount_threshold",
            name="Invoice Approval by Amount",
            combining_algorithm="deny_overrides",
            target={"resource.type": "invoice", "action": "create"},
            rules=[
                PolicyRule(
                    effect=Effect.DENY,
                    priority=100,
                    condition={
                        "resource.amount": {"gte": 1000000},  # 10 Lakh+
                        "subject.role": {"not_in": ["Super Admin", "Firm Admin", "Partner"]}
                    },
                    description="High-value invoices require Partner+ approval"
                ),
                PolicyRule(
                    effect=Effect.DENY,
                    priority=90,
                    condition={
                        "resource.amount": {"gte": 500000},  # 5 Lakh+
                        "subject.role": "Manager"
                    },
                    description="Managers limited to 5 Lakh invoices"
                ),
            ]
        ))
        
        # Policy: Compliance Filing Deadline
        self.add_policy(Policy(
            id="compliance_deadline",
            name="Compliance Filing Near Deadline",
            combining_algorithm="permit_overrides",
            target={"resource.type": "compliance_filing"},
            rules=[
                PolicyRule(
                    effect=Effect.ALLOW,
                    priority=100,
                    condition={
                        "resource.days_until_due": {"lte": 3},
                        "subject.role": {"in": ["Super Admin", "Firm Admin", "Partner", "Manager"]},
                        "action": {"in": ["read", "update", "file"]}
                    },
                    description="Urgent filings accessible to all managers+"
                ),
            ]
        ))
    
    def add_policy(self, policy: Policy):
        """Add a policy to the engine."""
        self.policies[policy.id] = policy
    
    def remove_policy(self, policy_id: str):
        """Remove a policy."""
        self.policies.pop(policy_id, None)
    
    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a policy by ID."""
        return self.policies.get(policy_id)
    
    def list_policies(self) -> List[Policy]:
        """List all policies."""
        return list(self.policies.values())
    
    async def evaluate(
        self,
        subject: Dict[str, Any],
        resource: Dict[str, Any],
        action: str,
        environment: Dict[str, Any] = None
    ) -> Effect:
        """
        Evaluate all policies for a request.
        Returns ALLOW or DENY.
        """
        attributes = self._build_attributes(subject, resource, action, environment)
        
        # Evaluate all policies
        results = []
        for policy in self.policies.values():
            result = policy.evaluate(attributes)
            results.append((policy.id, result))
        
        # Combine results (deny_overrides across policies)
        for policy_id, result in results:
            if result == Effect.DENY:
                return Effect.DENY
        
        # If any policy explicitly allows, allow
        for policy_id, result in results:
            if result == Effect.ALLOW:
                return Effect.ALLOW
        
        return Effect.DENY
    
    def _build_attributes(
        self,
        subject: Dict[str, Any],
        resource: Dict[str, Any],
        action: str,
        environment: Dict[str, Any] = None
    ) -> Dict[str, Attribute]:
        """Build attribute dictionary for evaluation."""
        attrs = {}
        
        # Subject attributes
        for key, value in subject.items():
            attrs[f"subject.{key}"] = Attribute(
                name=f"subject.{key}",
                value=value,
                category="subject"
            )
        
        # Resource attributes
        for key, value in resource.items():
            attrs[f"resource.{key}"] = Attribute(
                name=f"resource.{key}",
                value=value,
                category="resource"
            )
        
        # Action attributes
        attrs["action"] = Attribute(
            name="action",
            value=action,
            category="action"
        )
        
        # Environment attributes
        env = environment or {}
        env.setdefault("current_time", datetime.now(timezone.utc).isoformat())
        env.setdefault("business_hours", self._is_business_hours())
        
        for key, value in env.items():
            attrs[f"environment.{key}"] = Attribute(
                name=f"environment.{key}",
                value=value,
                category="environment"
            )
        
        return attrs
    
    def _is_business_hours(self) -> bool:
        """Check if current time is within business hours (9 AM - 6 PM IST)."""
        now = datetime.now(timezone.utc)
        # Convert to IST (UTC+5:30)
        ist_hour = (now.hour + 5) % 24
        ist_minute = now.minute + 30
        if ist_minute >= 60:
            ist_hour = (ist_hour + 1) % 24
            ist_minute -= 60
        
        current_time = time(ist_hour, ist_minute)
        start = time(9, 0)
        end = time(18, 0)
        return start <= current_time < end


# Global ABAC engine instance
abac_engine = ABACEngine()


# ============================================================
# Resource-Specific Attribute Resolvers
# ============================================================

class ResourceAttributeResolver:
    """Resolves resource attributes from database for ABAC evaluation."""
    
    @staticmethod
    async def resolve_client(client_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        doc = db.collection("clients").document(client_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            return None
        return {
            "id": client_id,
            "type": "client",
            "owner_id": data.get("engagement_manager"),
            "engagement_manager_id": data.get("engagement_manager"),
            "created_by": data.get("created_by"),
            "sensitivity": data.get("sensitivity", "normal"),
        }
    
    @staticmethod
    async def resolve_document(doc_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        doc = db.collection("documents").document(doc_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            return None
        return {
            "id": doc_id,
            "type": "document",
            "owner_id": data.get("uploaded_by"),
            "sensitivity": data.get("sensitivity", "normal"),
            "client_id": data.get("client_id"),
        }
    
    @staticmethod
    async def resolve_invoice(invoice_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        doc = db.collection("invoices").document(invoice_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            return None
        return {
            "id": invoice_id,
            "type": "invoice",
            "owner_id": data.get("created_by"),
            "amount": data.get("total", 0),
            "client_id": data.get("client_id"),
            "status": data.get("status"),
        }
    
    @staticmethod
    async def resolve_task(task_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        doc = db.collection("tasks").document(task_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            return None
        return {
            "id": task_id,
            "type": "task",
            "owner_id": data.get("created_by"),
            "assignee_id": data.get("assignee_id"),
            "status": data.get("status"),
            "priority": data.get("priority"),
        }
    
    @staticmethod
    async def resolve_compliance_filing(filing_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        doc = db.collection("compliance").document(filing_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            return None
        
        # Calculate days until due
        from datetime import datetime, timezone
        due_str = data.get("actual_due_date")
        days_until_due = 999
        if due_str:
            try:
                due_date = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                days_until_due = (due_date - datetime.now(timezone.utc)).days
            except Exception:
                pass
        
        return {
            "id": filing_id,
            "type": "compliance_filing",
            "owner_id": data.get("created_by"),
            "days_until_due": days_until_due,
            "status": data.get("status"),
            "compliance_code": data.get("compliance_code"),
        }
    
    @staticmethod
    async def resolve_bd_lead(lead_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        doc = db.collection("bd/leads").document(lead_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            return None
        return {
            "id": lead_id,
            "type": "bd_lead",
            "owner_id": data.get("owner"),
            "status": data.get("status"),
            "priority": data.get("priority"),
            "estimated_value": data.get("estimated_value", 0),
        }
    
    @staticmethod
    async def resolve_support_ticket(ticket_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        doc = db.collection("support_tickets").document(ticket_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            return None
        return {
            "id": ticket_id,
            "type": "support_ticket",
            "owner_id": data.get("created_by"),
            "assignee_id": data.get("assigned_to"),
            "status": data.get("status"),
            "priority": data.get("priority"),
            "category": data.get("category"),
        }


# ============================================================
# FastAPI Dependencies for ABAC
# ============================================================

async def require_abac_permission(
    resource_type: str,
    action: str,
    resource_id_param: str = "id"
):
    """
    FastAPI dependency for ABAC-based authorization.
    Resolves resource from DB and evaluates policies.
    """
    async def checker(
        request: Request,
        resource_id: str = None,
        user: dict = Depends(get_current_user)
    ):
        # Get resource_id from path params
        if resource_id is None:
            resource_id = request.path_params.get(resource_id_param)
        
        if not resource_id:
            raise HTTPException(400, "Resource ID required for ABAC check")
        
        tenant_id = get_current_tenant()
        
        # Build subject attributes
        subject = {
            "id": user.get("user_id"),
            "role": user.get("role"),
            "email": user.get("email"),
            "tenant_id": tenant_id,
        }
        
        # Resolve resource
        resolver_method = getattr(ResourceAttributeResolver, f"resolve_{resource_type}", None)
        if not resolver_method:
            raise HTTPException(500, f"No resolver for resource type: {resource_type}")
        
        resource = await resolver_method(resource_id, tenant_id)
        if not resource:
            raise HTTPException(404, f"{resource_type} not found")
        
        # Build environment
        environment = {
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "path": request.url.path,
            "method": request.method,
        }
        
        # Evaluate
        result = await abac_engine.evaluate(subject, resource, action, environment)
        
        if result == Effect.DENY:
            # Log denial
            from app.core.audit import log_audit
            await log_audit(
                tenant_id=tenant_id,
                actor_id=user.get("user_id"),
                action="ABAC_DENY",
                entity=f"abac/{resource_type}",
                entity_id=resource_id,
                diff={
                    "action": action,
                    "subject_role": user.get("role"),
                    "resource_type": resource_type,
                }
            )
            raise HTTPException(403, f"Access denied by ABAC policy for {action} on {resource_type}")
        
        # Store resolved resource in request state for downstream use
        request.state.abac_resource = resource
        return resource
    
    return checker


# Convenience dependencies for common patterns
def abac_read(resource_type: str, resource_id_param: str = "id"):
    return require_abac_permission(resource_type, "read", resource_id_param)

def abac_write(resource_type: str, resource_id_param: str = "id"):
    return require_abac_permission(resource_type, "write", resource_id_param)

def abac_delete(resource_type: str, resource_id_param: str = "id"):
    return require_abac_permission(resource_type, "delete", resource_id_param)

def abac_admin(resource_type: str, resource_id_param: str = "id"):
    return require_abac_permission(resource_type, "admin", resource_id_param)


# ============================================================
# Policy Management API (for admin UI)
# ============================================================

class PolicyManager:
    """Manage ABAC policies via API."""
    
    @staticmethod
    async def create_policy(policy: Policy) -> Policy:
        abac_engine.add_policy(policy)
        return policy
    
    @staticmethod
    async def update_policy(policy_id: str, policy: Policy) -> Policy:
        if policy_id not in abac_engine.policies:
            raise HTTPException(404, "Policy not found")
        abac_engine.add_policy(policy)
        return policy
    
    @staticmethod
    async def delete_policy(policy_id: str):
        if policy_id not in abac_engine.policies:
            raise HTTPException(404, "Policy not found")
        abac_engine.remove_policy(policy_id)
        return {"message": "Policy deleted"}
    
    @staticmethod
    async def list_policies() -> List[Policy]:
        return abac_engine.list_policies()
    
    @staticmethod
    async def get_policy(policy_id: str) -> Policy:
        policy = abac_engine.get_policy(policy_id)
        if not policy:
            raise HTTPException(404, "Policy not found")
        return policy
    
    @staticmethod
    async def test_policy(policy: Policy, test_attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Test a policy against sample attributes."""
        # Build attributes from test data
        attrs = {}
        for key, value in test_attributes.items():
            category = "subject" if key.startswith("subject.") else \
                      "resource" if key.startswith("resource.") else \
                      "action" if key == "action" else "environment"
            attrs[key] = Attribute(name=key, value=value, category=category)
        
        result = policy.evaluate(attrs)
        return {
            "policy_id": policy.id,
            "result": result.value,
            "matched_rules": [
                rule.description for rule in policy.rules
                if policy._matches_rule(rule, attrs)
            ]
        }