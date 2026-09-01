# Role-Based Access Control Engine
# PRD Matrix (PDF p.3): 7 roles × 5 entities (View, Create, Update, Delete, Export)
# Single-tenant mode enforces per-firm permissions; multi-tenant uses same logic per tenant

ROLES = ["Super Admin", "Firm Admin", "Partner", "Manager", "Article Assistant", "Paid Assistant", "Client"]

ENTITIES = ["clients", "tasks", "documents", "invoices", "credentials", "audit", "compliance"]

# Default permission matrix — used until Firestore rolePermissions collection is seeded
# Derived from PDF p.3 acceptance criteria
DEFAULT_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    # Super Admin: all permissions on all entities
    "Super Admin": {entity: ["view", "create", "update", "delete", "export"] for entity in ENTITIES},
    # Firm Admin: all permissions
    "Firm Admin":  {entity: ["view", "create", "update", "delete", "export"] for entity in ENTITIES},
    # Partner: all permissions (firm-level access)
    "Partner":     {entity: ["view", "create", "update", "delete", "export"] for entity in ENTITIES},
    # Manager: restricted permissions
    "Manager":     {
        "clients":       ["view", "create", "update"],
        "tasks":         ["view", "create", "update", "delete"],
        "documents":     ["view", "create", "update"],
        "invoices":      ["view"],
        "credentials":   ["view"],
        "audit":         ["view"],
        "compliance":    ["view", "create", "update"],
    },
    # Article Assistant: can view/create own resources, update own assignments
    "Article Assistant": {
        "clients":       ["view", "create"],
        "tasks":         ["view", "update"],
        "documents":     ["view"],
        "invoices":      [],
        "credentials":   [],
        "audit":         [],
        "compliance":    ["view"],
    },
    # Paid Assistant: limited view access
    "Paid Assistant": {
        "clients":       ["view"],
        "tasks":         ["view", "update"],
        "documents":     ["view"],
        "invoices":      [],
        "credentials":   [],
        "audit":         [],
        "compliance":    ["view"],
    },
    # Client: can only view own resources
    "Client": {
        "clients":       ["view"],
        "tasks":         ["view"],
        "documents":     ["view"],
        "invoices":      ["view"],
        "credentials":   [],
        "audit":         [],
        "compliance":    ["view"],
    },
}


def check_permission(role: str, entity: str, action: str) -> bool:
    """Check if a role has permission to perform an action on an entity."""
    allowed = DEFAULT_PERMISSIONS.get(role, {}).get(entity, [])
    return action in allowed


def require_permission(entity: str, action: str):
    """
    FastAPI dependency that enforces RBAC.
    Raises 403 if the authenticated user lacks the required permission.
    """
    from fastapi import Depends, HTTPException
    from app.core.auth import get_current_user

    async def wrapper(user=Depends(get_current_user)):
        role = user.get("role", "Client")
        if not check_permission(role, entity, action):
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: role '{role}' cannot {action} {entity}"
            )
        return user

    return wrapper
