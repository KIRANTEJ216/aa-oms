from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.schemas.auth import RegisterRequest, LoginRequest, FirebaseLoginRequest, MfaVerifyRequest, TokenResponse, ForgotPasswordRequest, MfaSetupResponse
from app.schemas.common import MessageResponse
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, create_temp_token, decode_token, generate_mfa_secret, provisioning_uri, qr_data_uri, verify_totp
from app.infra.firestore.client import get_db
from app.core.auth import get_current_user
from app.core.tenant import get_current_tenant
from app.core.audit import log_audit
from app.core.rate_limit import limiter, RATE_LIMITS
from app.core.auth_strong import PasswordPolicy, LoginAttemptTracker, SessionManager, PasswordReset
from app.core.bot_protection import verify_bot_protection, optional_bot_check
from app.core.api_keys import APIKeyManager, get_api_key, require_api_key_scope
from app.core.abac import abac_engine, require_abac_permission, Effect, Policy, PolicyRule
from app.core.passkeys import passkey_manager, PasskeyRegistrationStartRequest, PasskeyRegistrationCompleteRequest, PasskeyAuthenticationStartRequest, PasskeyAuthenticationCompleteRequest, PasskeyRenameRequest
from app.core.oauth2 import oauth2_manager, OAuth2AuthorizeRequest, OAuth2CallbackRequest, OAuth2LinkRequest

router = APIRouter()

@router.post("/register", response_model=MessageResponse, status_code=201)
@limiter.limit(RATE_LIMITS["auth_register"])
async def register(request: Request, body: RegisterRequest, bot_result: dict = Depends(verify_bot_protection)):
    # Validate password policy
    errors = PasswordPolicy.validate(body.password)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    
    db = get_db()
    tenant_id = get_current_tenant()
    # Check duplicate email within tenant
    existing = list(db.collection("users").where("tenant_id", "==", tenant_id).where("email", "==", body.email.lower()).limit(1).stream())
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists in this firm")
    user_id = str(uuid.uuid4())
    db.collection("users").document(user_id).set({
        "tenant_id": tenant_id,
        "name": body.name,
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "role": "Client",  # default; admin upgrades
        "mobile": body.mobile,
        "mfaEnabled": False,
        "mfaSecretEnc": None,
        "isActive": True,
        "emailVerified": False,
        "createdAt": datetime.now(timezone.utc),
        "lastLoginAt": None,
    })
    await log_audit(tenant_id=tenant_id, actor_id=user_id, action="CREATE", entity="users", entity_id=user_id)
    
    # Send email verification if required
    from app.core.config import get_settings
    if get_settings().email_verification_required:
        from app.core.auth_strong import EmailVerification
        await EmailVerification.send_verification(user_id, body.email.lower(), tenant_id)
    
    return {"message": "Account created. Please verify your email address."}

@router.post("/login")
@limiter.limit(RATE_LIMITS["auth_login"])
async def login(request: Request, body: LoginRequest, bot_result: dict = Depends(verify_bot_protection)):
    # Get client IP for login tracking
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # Check for account lockout
    locked, lockout_msg = await LoginAttemptTracker.is_locked(client_ip, body.email)
    if locked:
        raise HTTPException(status_code=429, detail=lockout_msg)
    
    db = get_db()
    tenant_id = get_current_tenant()
    # Find user by email within tenant
    docs = list(db.collection("users").where("tenant_id", "==", tenant_id).where("email", "==", body.email.lower()).limit(1).stream())
    if not docs:
        # Fallback: global search (for seed without tenant filter in stub)
        docs = list(db.collection("users").where("email", "==", body.email.lower()).limit(1).stream())
    if not docs:
        # Record failed attempt (prevent user enumeration by always checking)
        await LoginAttemptTracker.record_failure(client_ip, body.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    data = docs[0].to_dict()
    # The stub stores docs without id; try to get id from doc
    user_id = getattr(docs[0], "id", None) or data.get("user_id") or "unknown"
    # In-memory stub: need to find actual doc id via store scan
    if user_id == "unknown":
        try:
            # brute force: find in store
            store = getattr(db, "store", {})
            for (col, doc_id), v in store.items():
                if col == "users" and v.get("email") == body.email.lower():
                    user_id = doc_id
                    data = v
                    break
        except Exception:
            pass
    if not verify_password(body.password, data.get("password_hash","")):
        await LoginAttemptTracker.record_failure(client_ip, body.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not data.get("isActive", True):
        raise HTTPException(status_code=403, detail="Account disabled")
    
    # Check email verification
    from app.core.config import get_settings
    if get_settings().email_verification_required and not data.get("emailVerified", False):
        raise HTTPException(status_code=403, detail="Email not verified. Please check your inbox.")
    
    actual_tenant = data.get("tenant_id", tenant_id)
    # MFA check
    if data.get("mfaEnabled") and data.get("mfaSecretEnc"):
        from app.infra.secrets.client import decrypt_value
        # mfaSecretEnc is base64 stub; decrypt
        temp = create_temp_token(user_id=user_id, tenant_id=actual_tenant)
        await LoginAttemptTracker.clear(client_ip, body.email)
        return {"mfa_required": True, "temp_token": temp}
    
    # Clear failed attempts on successful password
    await LoginAttemptTracker.clear(client_ip, body.email)
    
    # Create session
    session_id = await SessionManager.create_session(
        user_id=user_id,
        tenant_id=actual_tenant,
        device_info={},  # Could parse from user_agent
        ip=client_ip,
        user_agent=user_agent
    )
    
    access = create_access_token(user_id=user_id, tenant_id=actual_tenant, role=data.get("role","Client"), email=data.get("email"))
    refresh = create_refresh_token(user_id=user_id, tenant_id=actual_tenant)
    # Update lastLogin
    try:
        db.collection("users").document(user_id).set({"lastLoginAt": datetime.now(timezone.utc)}, merge=True)
    except Exception:
        pass
    await log_audit(tenant_id=actual_tenant, actor_id=user_id, action="LOGIN", entity="auth", entity_id=user_id, ip=client_ip)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "session_id": session_id}

@router.post("/firebase")  # Hybrid auth: verify Firebase ID token, issue custom JWTs
@limiter.limit(RATE_LIMITS["auth_firebase"])
async def firebase_login(request: Request, body: FirebaseLoginRequest, bot_result: dict = Depends(verify_bot_protection)):
    from app.infra.firebase.client import verify_id_token
    db = get_db()
    tenant_id = get_current_tenant()
    try:
        fb = verify_id_token(body.id_token)
    except RuntimeError as e:
        # Firebase not configured on this deployment
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {e}")
    email = (fb.get("email") or "").lower()
    fb_uid = fb.get("uid")
    if not email and not fb_uid:
        raise HTTPException(status_code=400, detail="Firebase token has no email")
    # Match local user by email (tenant-scoped, fall back to global for seed)
    docs = list(db.collection("users").where("tenant_id", "==", tenant_id).where("email", "==", email).limit(1).stream()) if email else []
    if not docs and email:
        docs = list(db.collection("users").where("email", "==", email).limit(1).stream())
    if docs:
        user_id = getattr(docs[0], "id", None) or "unknown"
        data = docs[0].to_dict()
        if user_id == "unknown":
            # In-memory stub: scan store for actual doc id
            try:
                store = getattr(db, "store", {})
                for (col, doc_id), v in store.items():
                    if col == "users" and v.get("email") == email:
                        user_id = doc_id; data = v; break
            except Exception:
                pass
        if not data.get("isActive", True):
            raise HTTPException(status_code=403, detail="Account disabled")
        actual_tenant = data.get("tenant_id", tenant_id)
        role = data.get("role", "Client")
    else:
        # Auto-provision a Client account on first Firebase sign-in
        from app.core.config import get_settings
        if not get_settings().firebase_auto_provision:
            raise HTTPException(status_code=401, detail="No local account matches this Firebase identity")
        if email:
            user_id = str(uuid.uuid4())
            db.collection("users").document(user_id).set({
                "tenant_id": tenant_id, "name": fb.get("name", email.split("@")[0]), "email": email,
                "password_hash": "", "role": "Client", "mobile": "",
                "mfaEnabled": False, "mfaSecretEnc": None, "isActive": True,
                "firebase_uid": fb_uid, "authProvider": "firebase",
                "createdAt": datetime.now(timezone.utc), "lastLoginAt": None,
            })
            actual_tenant = tenant_id
            role = "Client"
            print(f"[firebase-login] auto-provisioned client: {email}")
        else:
            raise HTTPException(status_code=401, detail="No local account matches this Firebase identity")
    access = create_access_token(user_id=user_id, tenant_id=actual_tenant, role=role, email=email)
    refresh = create_refresh_token(user_id=user_id, tenant_id=actual_tenant)
    try:
        db.collection("users").document(user_id).set({"lastLoginAt": datetime.now(timezone.utc)}, merge=True)
    except Exception:
        pass
    await log_audit(tenant_id=actual_tenant, actor_id=user_id, action="LOGIN", entity="auth/firebase", entity_id=user_id)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/firebase/register")  # Hybrid: register a local account from a Firebase identity
@limiter.limit(RATE_LIMITS["auth_register"])
async def firebase_register(request: Request, body: FirebaseLoginRequest, bot_result: dict = Depends(verify_bot_protection)):
    from app.infra.firebase.client import verify_id_token
    db = get_db()
    tenant_id = get_current_tenant()
    try:
        fb = verify_id_token(body.id_token)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {e}")
    email = (fb.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Firebase token has no email")
    existing = list(db.collection("users").where("tenant_id", "==", tenant_id).where("email", "==", email).limit(1).stream())
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists in this firm")
    user_id = str(uuid.uuid4())
    db.collection("users").document(user_id).set({
        "tenant_id": tenant_id, "name": fb.get("name", email.split("@")[0]), "email": email,
        "password_hash": "", "role": "Client", "mobile": "",
        "mfaEnabled": False, "mfaSecretEnc": None, "isActive": True,
        "firebase_uid": fb.get("uid"), "authProvider": "firebase",
        "createdAt": datetime.now(timezone.utc), "lastLoginAt": None,
    })
    await log_audit(tenant_id=tenant_id, actor_id=user_id, action="CREATE", entity="users", entity_id=user_id)
    return {"message": "Account created via Firebase. Awaiting approval."}

@router.post("/mfa/setup", response_model=MfaSetupResponse)
@limiter.limit(RATE_LIMITS["auth_mfa"])
async def mfa_setup(request: Request):
    from app.core.auth import get_current_user
    from fastapi import Depends
    # This is a placeholder — proper impl requires auth dependency injection at router level
    # For now return a generated secret (caller must be authenticated via separate flow)
    secret = generate_mfa_secret()
    # In real flow: save to user doc, return QR
    # Here we just return for testing
    return {"secret": secret, "provisioning_uri": provisioning_uri(secret, "user@caoms.in"), "qr_data_uri": qr_data_uri(provisioning_uri(secret, "user@caoms.in"))}

@router.post("/mfa/verify")
@limiter.limit(RATE_LIMITS["auth_mfa"])
async def mfa_verify(request: Request, body: MfaVerifyRequest):
    try:
        payload = decode_token(body.temp_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid temp token: {e}")
    if payload.get("type") != "temp":
        raise HTTPException(status_code=401, detail="Not a temp token")
    user_id = payload.get("sub"); tenant_id = payload.get("tenant_id")
    db = get_db()
    try:
        doc = db.collection("users").document(user_id).get()
        data = doc.to_dict() if doc.exists else {}
    except Exception:
        data = {}
    # Try stub
    if not data:
        try:
            store = getattr(db, "store", {})
            data = store.get(("users", user_id), {})
        except Exception:
            data = {}
    secret_enc = data.get("mfaSecretEnc")
    if not secret_enc:
        raise HTTPException(status_code=400, detail="MFA not set up for this user")
    from app.infra.secrets.client import decrypt_value
    secret = decrypt_value(secret_enc)
    if not verify_totp(secret, body.code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")
    # Issue real tokens
    access = create_access_token(user_id=user_id, tenant_id=tenant_id, role=data.get("role","Client"), email=data.get("email",""))
    refresh = create_refresh_token(user_id=user_id, tenant_id=tenant_id)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/refresh")
@limiter.limit(RATE_LIMITS["auth_refresh"])
async def refresh(request: Request, body: dict):
    token = body.get("refresh_token")
    if not token:
        raise HTTPException(status_code=400, detail="refresh_token required")
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user_id = payload.get("sub"); tenant_id = payload.get("tenant_id")
    # Re-read role from Firestore
    role = payload.get("role", "Client")
    email = payload.get("email", "")
    try:
        db = get_db()
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            d = doc.to_dict()
            role = d.get("role", role); email = d.get("email", email)
    except Exception:
        pass
    access = create_access_token(user_id=user_id, tenant_id=tenant_id, role=role, email=email)
    return {"access_token": access, "token_type": "bearer"}

@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(RATE_LIMITS["auth_forgot"])
async def forgot_password(request: Request, body: ForgotPasswordRequest, bot_result: dict = Depends(verify_bot_protection)):
    client_ip = request.client.host if request.client else "unknown"
    tenant_id = get_current_tenant()
    return await PasswordReset.request_reset(body.email, tenant_id, client_ip, request.headers.get("user-agent", ""))

# Password Reset Verification
class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, request: Request, bot_result: dict = Depends(verify_bot_protection)):
    client_ip = request.client.host if request.client else "unknown"
    # Find user by token - we need to check all users (or store token with user_id)
    # For now, require user_id in request or store token->user mapping
    # This is a simplified version
    db = get_db()
    # In production, you'd have a token->user_id mapping
    raise HTTPException(status_code=501, detail="Use /reset-password/{user_id} with token in body")

@router.post("/reset-password/{user_id}", response_model=MessageResponse)
async def reset_password_with_user(user_id: str, body: ResetPasswordRequest, request: Request, bot_result: dict = Depends(verify_bot_protection)):
    client_ip = request.client.host if request.client else "unknown"
    tenant_id = get_current_tenant()
    
    # Verify tenant
    db = get_db()
    doc = db.collection("users").document(user_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    
    success = await PasswordReset.reset_password(user_id, body.token, body.new_password, client_ip)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    return {"message": "Password has been reset. Please log in with your new password."}

# Email Verification
class VerifyEmailRequest(BaseModel):
    token: str

@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(body: VerifyEmailRequest, request: Request, bot_result: dict = Depends(verify_bot_protection)):
    # For anonymous verification, we need to find user by token
    # In production, store token->user_id mapping
    raise HTTPException(status_code=501, detail="Use /verify-email/{user_id} with token in body")

@router.post("/verify-email/{user_id}", response_model=MessageResponse)
async def verify_email_with_user(user_id: str, body: VerifyEmailRequest, request: Request, bot_result: dict = Depends(verify_bot_protection)):
    tenant_id = get_current_tenant()
    
    db = get_db()
    doc = db.collection("users").document(user_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    if doc.to_dict().get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    
    from app.core.auth_strong import EmailVerification
    success = await EmailVerification.verify(user_id, body.token)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    
    return {"message": "Email verified successfully. You can now log in."}

@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit(RATE_LIMITS["auth_forgot"])
async def resend_verification(request: Request, body: ForgotPasswordRequest, bot_result: dict = Depends(verify_bot_protection)):
    """Resend verification email (reuses forgot-password rate limit)."""
    tenant_id = get_current_tenant()
    
    db = get_db()
    docs = list(db.collection("users").where("tenant_id", "==", tenant_id).where("email", "==", body.email.lower()).limit(1).stream())
    if not docs:
        return {"message": "If the account exists, a verification email has been sent."}
    
    user_id = docs[0].id
    from app.core.auth_strong import EmailVerification
    await EmailVerification.send_verification(user_id, body.email.lower(), tenant_id)
    return {"message": "If the account exists, a verification email has been sent."}

# Session Management
@router.get("/sessions")
async def list_sessions(request: Request):
    """List current user's active sessions."""
    from app.core.auth import get_current_user
    from fastapi import Depends
    
    # This needs proper auth dependency - simplified for now
    # In production, use Depends(get_current_user)
    raise HTTPException(status_code=501, detail="Requires authenticated user context")

@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, request: Request):
    """Revoke a specific session."""
    from app.core.auth import get_current_user
    from fastapi import Depends
    from app.core.auth_strong import SessionManager
    
    raise HTTPException(status_code=501, detail="Requires authenticated user context")

@router.delete("/sessions")
async def revoke_all_sessions(request: Request):
    """Revoke all sessions except current."""
    from app.core.auth import get_current_user
    from fastapi import Depends
    from app.core.auth_strong import SessionManager
    
    raise HTTPException(status_code=501, detail="Requires authenticated user context")

# Password Change (authenticated)
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password", response_model=MessageResponse)
async def change_password(request: Request, body: ChangePasswordRequest):
    """Change password for authenticated user."""
    from app.core.auth import get_current_user
    from fastapi import Depends
    from app.core.auth_strong import change_password as change_pwd
    
    raise HTTPException(status_code=501, detail="Requires authenticated user context")

# ============================================================
# API Key Management Endpoints
# ============================================================

class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default_factory=list)
    expires_days: int = Field(default=365, ge=1, le=3650)
    description: str = Field(default="", max_length=500)

class CreateAPIKeyResponse(BaseModel):
    key_id: str
    raw_key: str
    name: str
    scopes: List[str]
    expires_at: str
    created_at: str
    warning: str

class APIKeyResponse(BaseModel):
    key_id: str
    name: str
    scopes: List[str]
    expires_at: str
    created_at: str
    last_used_at: Optional[str] = None
    revoked: bool

class RevokeAPIKeyRequest(BaseModel):
    reason: str = Field(default="manual", max_length=200)

class RotateAPIKeyRequest(BaseModel):
    expires_days: int = Field(default=365, ge=1, le=3650)

@router.post("/api-keys", response_model=CreateAPIKeyResponse, status_code=201)
@limiter.limit("10/minute")
async def create_api_key(request: Request, body: CreateAPIKeyRequest, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Create a new API key (requires admin:all scope)."""
    tenant_id = get_current_tenant()
    user_id = key_info.get("user_id")
    
    result = await APIKeyManager.create_key(
        name=body.name,
        tenant_id=tenant_id,
        user_id=user_id,
        scopes=body.scopes,
        expires_days=body.expires_days,
        description=body.description
    )
    return result

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(request: Request, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """List all API keys for the tenant (requires admin:all scope)."""
    tenant_id = get_current_tenant()
    user_id = key_info.get("user_id")
    
    keys = await APIKeyManager.list_keys(tenant_id, user_id)
    return keys

@router.get("/api-keys/{key_id}", response_model=APIKeyResponse)
async def get_api_key_detail(key_id: str, request: Request, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Get API key details (requires admin:all scope)."""
    tenant_id = get_current_tenant()
    
    db = get_db()
    doc = db.collection("apiKeys").document(key_id).get()
    if not doc.exists:
        raise HTTPException(404, "API key not found")
    
    data = doc.to_dict()
    if data.get("tenant_id") != tenant_id:
        raise HTTPException(403, "Tenant mismatch")
    
    data["key_id"] = doc.id
    data.pop("key_hash", None)
    data.pop("salt", None)
    return data

@router.delete("/api-keys/{key_id}", response_model=MessageResponse)
@limiter.limit("10/minute")
async def revoke_api_key(key_id: str, request: Request, body: RevokeAPIKeyRequest, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Revoke an API key (requires admin:all scope)."""
    tenant_id = get_current_tenant()
    user_id = key_info.get("user_id")
    
    success = await APIKeyManager.revoke_key(key_id, tenant_id, user_id, body.reason)
    if not success:
        raise HTTPException(404, "API key not found")
    
    return {"message": "API key revoked successfully"}

@router.post("/api-keys/{key_id}/rotate", response_model=CreateAPIKeyResponse)
@limiter.limit("5/minute")
async def rotate_api_key(key_id: str, request: Request, body: RotateAPIKeyRequest, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Rotate an API key - revoke old, create new with same scopes (requires admin:all scope)."""
    tenant_id = get_current_tenant()
    user_id = key_info.get("user_id")
    
    result = await APIKeyManager.rotate_key(key_id, tenant_id, user_id, body.expires_days)
    return result

# Public endpoint to validate an API key (for testing)
class ValidateAPIKeyRequest(BaseModel):
    api_key: str

@router.post("/api-keys/validate")
@limiter.limit("20/minute")
async def validate_api_key(request: Request, body: ValidateAPIKeyRequest):
    """Validate an API key (public endpoint for testing)."""
    key_info = await APIKeyManager.validate_key(body.api_key)
    if not key_info:
        return {"valid": False, "reason": "Invalid, expired, or revoked"}
    
    return {
        "valid": True,
        "key_id": key_info.get("key_id"),
        "name": key_info.get("name"),
        "scopes": key_info.get("scopes"),
        "expires_at": key_info.get("expires_at"),
    }


# ============================================================
# ABAC Policy Management (Admin Only)
# ============================================================

class PolicyCreateRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    combining_algorithm: str = "deny_overrides"
    target: Dict[str, Any] = {}
    rules: List[Dict[str, Any]] = []

class PolicyTestRequest(BaseModel):
    policy: PolicyCreateRequest
    test_attributes: Dict[str, Any]

@router.get("/abac/policies")
@limiter.limit("20/minute")
async def list_abac_policies(request: Request, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """List all ABAC policies."""
    policies = abac_engine.list_policies()
    return [
        {
            "id": p.id,
            "name": p.name,
            "combining_algorithm": p.combining_algorithm,
            "target": p.target,
            "rules_count": len(p.rules),
        }
        for p in policies
    ]

@router.get("/abac/policies/{policy_id}")
@limiter.limit("20/minute")
async def get_abac_policy(policy_id: str, request: Request, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Get ABAC policy details."""
    policy = abac_engine.get_policy(policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return {
        "id": policy.id,
        "name": policy.name,
        "combining_algorithm": policy.combining_algorithm,
        "target": policy.target,
        "rules": [
            {
                "effect": rule.effect.value,
                "priority": rule.priority,
                "condition": rule.condition,
                "description": rule.description,
            }
            for rule in policy.rules
        ],
    }

@router.post("/abac/policies", status_code=201)
@limiter.limit("10/minute")
async def create_abac_policy(request: Request, body: PolicyCreateRequest, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Create a new ABAC policy."""
    policy = Policy(
        id=body.id,
        name=body.name,
        combining_algorithm=body.combining_algorithm,
        target=body.target,
        rules=[
            PolicyRule(
                effect=Effect(r["effect"]),
                priority=r.get("priority", 0),
                condition=r["condition"],
                description=r.get("description", ""),
            )
            for r in body.rules
        ],
    )
    abac_engine.add_policy(policy)
    return {"message": "Policy created", "policy_id": policy.id}

@router.put("/abac/policies/{policy_id}")
@limiter.limit("10/minute")
async def update_abac_policy(policy_id: str, request: Request, body: PolicyCreateRequest, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Update an ABAC policy."""
    if policy_id not in abac_engine.policies:
        raise HTTPException(404, "Policy not found")
    policy = Policy(
        id=body.id,
        name=body.name,
        combining_algorithm=body.combining_algorithm,
        target=body.target,
        rules=[
            PolicyRule(
                effect=Effect(r["effect"]),
                priority=r.get("priority", 0),
                condition=r["condition"],
                description=r.get("description", ""),
            )
            for r in body.rules
        ],
    )
    abac_engine.add_policy(policy)
    return {"message": "Policy updated"}

@router.delete("/abac/policies/{policy_id}")
@limiter.limit("10/minute")
async def delete_abac_policy(policy_id: str, request: Request, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Delete an ABAC policy."""
    if policy_id not in abac_engine.policies:
        raise HTTPException(404, "Policy not found")
    abac_engine.remove_policy(policy_id)
    return {"message": "Policy deleted"}

@router.post("/abac/policies/test")
@limiter.limit("20/minute")
async def test_abac_policy(request: Request, body: PolicyTestRequest, key_info: dict = Depends(require_api_key_scope("admin:all"))):
    """Test a policy against sample attributes."""
    policy = Policy(
        id=body.policy.id,
        name=body.policy.name,
        combining_algorithm=body.policy.combining_algorithm,
        target=body.policy.target,
        rules=[
            PolicyRule(
                effect=Effect(r["effect"]),
                priority=r.get("priority", 0),
                condition=r["condition"],
                description=r.get("description", ""),
            )
            for r in body.policy.rules
        ],
    )
    result = policy.evaluate(body.test_attributes)
    return {
        "result": result.value,
        "matched_rules": [
            rule.description for rule in policy.rules
            if policy._matches_rule(rule, body.test_attributes)
        ]
    }

# ABAC Authorization Check (for resource access)
class AbacCheckRequest(BaseModel):
    resource_type: str
    resource_id: str
    action: str

@router.post("/abac/check")
@limiter.limit("50/minute")
async def check_abac_permission(request: Request, body: AbacCheckRequest, user: dict = Depends(get_current_user)):
    """Check ABAC permission for current user on a resource."""
    from app.core.abac import ResourceAttributeResolver
    
    tenant_id = get_current_tenant()
    resolver_method = getattr(ResourceAttributeResolver, f"resolve_{body.resource_type}", None)
    if not resolver_method:
        raise HTTPException(400, f"No resolver for resource type: {body.resource_type}")
    
    resource = await resolver_method(body.resource_id, tenant_id)
    if not resource:
        raise HTTPException(404, f"{body.resource_type} not found")
    
    subject = {
        "id": user.get("user_id"),
        "role": user.get("role"),
        "email": user.get("email"),
        "tenant_id": tenant_id,
    }
    
    result = await abac_engine.evaluate(subject, resource, body.action)
    return {
        "allowed": result == Effect.ALLOW,
        "resource_type": body.resource_type,
        "resource_id": body.resource_id,
        "action": body.action,
    }


# ============================================================
# Passkeys (WebAuthn) Endpoints
# ============================================================

@router.post("/passkeys/register/start")
@limiter.limit("10/minute")
async def passkey_register_start(request: Request, body: PasskeyRegistrationStartRequest, user: dict = Depends(get_current_user)):
    """Start passkey registration."""
    tenant_id = get_current_tenant()
    user_id = user.get("user_id")
    username = user.get("email")
    display_name = body.display_name or user.get("name") or username
    
    result = await passkey_manager.start_registration(user_id, username, display_name, tenant_id)
    return result

@router.post("/passkeys/register/complete")
@limiter.limit("10/minute")
async def passkey_register_complete(request: Request, body: PasskeyRegistrationCompleteRequest, user: dict = Depends(get_current_user)):
    """Complete passkey registration."""
    tenant_id = get_current_tenant()
    user_id = user.get("user_id")
    
    result = await passkey_manager.complete_registration(
        body.challenge_id,
        body.credential,
        user_id,
        tenant_id,
        body.device_name
    )
    return result

@router.post("/passkeys/authenticate/start")
@limiter.limit("10/minute")
async def passkey_authenticate_start(request: Request, body: PasskeyAuthenticationStartRequest):
    """Start passkey authentication (usernameless)."""
    tenant_id = get_current_tenant()
    username = body.username
    
    result = await passkey_manager.start_authentication(username, tenant_id)
    return result

@router.post("/passkeys/authenticate/complete")
@limiter.limit("10/minute")
async def passkey_authenticate_complete(request: Request, body: PasskeyAuthenticationCompleteRequest):
    """Complete passkey authentication."""
    tenant_id = get_current_tenant()
    
    result = await passkey_manager.complete_authentication(
        body.challenge_id,
        body.credential,
        tenant_id
    )
    return result

@router.get("/passkeys")
@limiter.limit("20/minute")
async def list_passkeys(request: Request, user: dict = Depends(get_current_user)):
    """List user's passkeys."""
    tenant_id = get_current_tenant()
    user_id = user.get("user_id")
    
    passkeys = await passkey_manager.list_credentials(user_id, tenant_id)
    return {"passkeys": passkeys}

@router.put("/passkeys/{credential_id}")
@limiter.limit("10/minute")
async def rename_passkey(credential_id: str, request: Request, body: PasskeyRenameRequest, user: dict = Depends(get_current_user)):
    """Rename a passkey."""
    tenant_id = get_current_tenant()
    user_id = user.get("user_id")
    
    await passkey_manager.rename_credential(credential_id, user_id, tenant_id, body.new_name)
    return {"message": "Passkey renamed"}

@router.delete("/passkeys/{credential_id}")
@limiter.limit("10/minute")
async def delete_passkey(credential_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Delete a passkey."""
    tenant_id = get_current_tenant()
    user_id = user.get("user_id")
    
    success = await passkey_manager.delete_credential(credential_id, user_id, tenant_id)
    if not success:
        raise HTTPException(404, "Passkey not found")
    return {"message": "Passkey deleted"}


# ============================================================
# OAuth2/OIDC Endpoints
# ============================================================

@router.get("/oauth/providers")
@limiter.limit("20/minute")
async def list_oauth_providers(request: Request):
    """List available OAuth2/OIDC providers."""
    providers = oauth2_manager.list_providers()
    return {"providers": providers}

@router.post("/oauth/authorize")
@limiter.limit("20/minute")
async def oauth_authorize(request: Request, body: OAuth2AuthorizeRequest):
    """Generate OAuth2 authorization URL."""
    from app.core.config import get_settings
    settings = get_settings()
    redirect_uri = body.redirect_uri or settings.oauth_redirect_uri
    
    # Generate PKCE pair
    code_verifier, code_challenge = generate_pkce_pair()
    
    # Store code_verifier in session/state
    state = body.state or secrets.token_urlsafe(32)
    nonce = body.nonce or secrets.token_urlsafe(16)
    
    # Store PKCE data
    db = get_db()
    db.collection("oauth2States").document(state).set({
        "provider": body.provider,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
        "nonce": nonce,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
    })
    
    result = oauth2_manager.get_authorization_url(
        body.provider,
        redirect_uri,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
    )
    result["code_verifier"] = code_verifier  # Return to client for storage
    return result

@router.post("/oauth/callback")
@limiter.limit("20/minute")
async def oauth_callback(request: Request, body: OAuth2CallbackRequest):
    """Handle OAuth2 callback and exchange code for tokens."""
    db = get_db()
    
    # Retrieve stored state
    state_doc = db.collection("oauth2States").document(body.state).get()
    if not state_doc.exists:
        raise HTTPException(400, "Invalid or expired state")
    
    state_data = state_doc.to_dict()
    if state_data.get("provider") != body.provider:
        raise HTTPException(400, "Provider mismatch")
    if state_data.get("redirect_uri") != body.redirect_uri:
        raise HTTPException(400, "Redirect URI mismatch")
    
    # Check expiry
    expires = state_data.get("expires_at")
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(400, "State expired")
    
    # Verify PKCE
    code_verifier = body.code_verifier or state_data.get("code_verifier")
    if code_verifier:
        # In production, we'd verify the code_challenge was used
        pass
    
    # Exchange code for tokens
    token_data = await oauth2_manager.exchange_code_for_tokens(
        body.provider,
        body.code,
        body.redirect_uri,
        code_verifier
    )
    
    # Get user info
    access_token = token_data.get("access_token")
    id_token = token_data.get("id_token")
    
    userinfo = await oauth2_manager.get_userinfo(body.provider, access_token)
    
    # Validate ID token if present
    if id_token:
        nonce = state_data.get("nonce")
        await oauth2_manager.validate_id_token(body.provider, id_token, nonce)
    
    # Find or create user
    tenant_id = get_current_tenant()
    result = await oauth2_manager.find_or_create_user(
        body.provider,
        userinfo,
        tenant_id,
        id_token
    )
    
    # Generate app tokens
    user_id = result["user_id"]
    user_data = result["user_data"]
    actual_tenant = user_data.get("tenant_id", tenant_id)
    role = user_data.get("role", "Client")
    email = user_data.get("email")
    
    from app.core.security import create_access_token, create_refresh_token
    access = create_access_token(user_id=user_id, tenant_id=actual_tenant, role=role, email=email)
    refresh = create_refresh_token(user_id=user_id, tenant_id=actual_tenant)
    
    # Create session
    session_id = await SessionManager.create_session(
        user_id=user_id,
        tenant_id=actual_tenant,
        device_info={"type": "oauth", "provider": body.provider},
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")
    )
    
    # Clean up state
    db.collection("oauth2States").document(body.state).delete()
    
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "session_id": session_id,
        "user": {
            "id": user_id,
            "email": email,
            "name": user_data.get("name"),
            "role": role,
            "provider": body.provider,
            "new_user": result.get("new_user", False),
        }
    }

@router.post("/oauth/link")
@limiter.limit("10/minute")
async def oauth_link_account(request: Request, body: OAuth2LinkRequest, user: dict = Depends(get_current_user)):
    """Link an OAuth2 provider to current account."""
    tenant_id = get_current_tenant()
    user_id = user.get("user_id")
    
    # Get userinfo from provider
    userinfo = await oauth2_manager.get_userinfo(body.provider, body.access_token)
    provider = oauth2_manager.get_provider(body.provider)
    
    provider_user_id = userinfo.get(provider.user_id_field)
    email = userinfo.get(provider.email_field, "").lower()
    
    if not provider_user_id:
        raise HTTPException(400, "Provider user ID not found")
    
    # Check if already linked
    db = get_db()
    existing = list(db.collection("userIdentities")
                   .where("provider_id", "==", body.provider)
                   .where("provider_user_id", "==", provider_user_id)
                   .limit(1)
                   .stream())
    if existing:
        raise HTTPException(409, "This provider account is already linked")
    
    # Create identity link
    identity_id = secrets.token_urlsafe(16)
    db.collection("userIdentities").document(identity_id).set({
        "user_id": user_id,
        "tenant_id": tenant_id,
        "provider_id": body.provider,
        "provider_user_id": provider_user_id,
        "email": email,
        "created_at": datetime.now(timezone.utc),
        "last_used_at": datetime.now(timezone.utc),
    })
    
    await log_audit(
        tenant_id=tenant_id,
        actor_id=user_id,
        action="OAUTH_LINK",
        entity="userIdentities",
        entity_id=identity_id,
        diff={"provider": body.provider}
    )
    
    return {"message": "Account linked successfully"}

@router.get("/oauth/linked")
@limiter.limit("20/minute")
async def list_linked_accounts(request: Request, user: dict = Depends(get_current_user)):
    """List linked OAuth2 accounts."""
    tenant_id = get_current_tenant()
    user_id = user.get("user_id")
    
    db = get_db()
    links = list(db.collection("userIdentities")
                .where("user_id", "==", user_id)
                .where("tenant_id", "==", tenant_id)
                .stream())
    
    return {
        "linked_accounts": [
            {
                "provider": link.to_dict().get("provider_id"),
                "email": link.to_dict().get("email"),
                "linked_at": link.to_dict().get("created_at"),
            }
            for link in links
        ]
    }

@router.delete("/oauth/linked/{provider}")
@limiter.limit("10/minute")
async def unlink_account(provider: str, request: Request, user: dict = Depends(get_current_user)):
    """Unlink an OAuth2 provider."""
    tenant_id = get_current_tenant()
    user_id = user.get("user_id")
    
    db = get_db()
    links = list(db.collection("userIdentities")
                .where("user_id", "==", user_id)
                .where("tenant_id", "==", tenant_id)
                .where("provider_id", "==", provider)
                .limit(1)
                .stream())
    
    for link in links:
        link.reference.delete()
        await log_audit(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="OAUTH_UNLINK",
            entity="userIdentities",
            entity_id=link.id,
            diff={"provider": provider}
        )
        return {"message": "Account unlinked"}
    
    raise HTTPException(404, "Linked account not found")
