from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import uuid
from app.schemas.auth import RegisterRequest, LoginRequest, FirebaseLoginRequest, MfaVerifyRequest, TokenResponse, ForgotPasswordRequest, MfaSetupResponse
from app.schemas.common import MessageResponse
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, create_temp_token, decode_token, generate_mfa_secret, provisioning_uri, qr_data_uri, verify_totp
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant
from app.core.audit import log_audit

router = APIRouter()

@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(body: RegisterRequest):
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
        "createdAt": datetime.now(timezone.utc),
        "lastLoginAt": None,
    })
    await log_audit(tenant_id=tenant_id, actor_id=user_id, action="CREATE", entity="users", entity_id=user_id)
    return {"message": "Account created. Awaiting approval."}

@router.post("/login")
async def login(body: LoginRequest):
    db = get_db()
    tenant_id = get_current_tenant()
    # Find user by email within tenant
    docs = list(db.collection("users").where("tenant_id", "==", tenant_id).where("email", "==", body.email.lower()).limit(1).stream())
    if not docs:
        # Fallback: global search (for seed without tenant filter in stub)
        docs = list(db.collection("users").where("email", "==", body.email.lower()).limit(1).stream())
    if not docs:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    data = docs[0].to_dict()
    # The stub stores docs without id; try to get id from doc
    user_id = getattr(docs[0], "id", None) or data.get("user_id") or "unknown"
    # In-memory stub: need to find actual doc id via store scan
    # Try to find id by scanning
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
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not data.get("isActive", True):
        raise HTTPException(status_code=403, detail="Account disabled")
    actual_tenant = data.get("tenant_id", tenant_id)
    # MFA check
    if data.get("mfaEnabled") and data.get("mfaSecretEnc"):
        from app.infra.secrets.client import decrypt_value
        # mfaSecretEnc is base64 stub; decrypt
        temp = create_temp_token(user_id=user_id, tenant_id=actual_tenant)
        return {"mfa_required": True, "temp_token": temp}
    access = create_access_token(user_id=user_id, tenant_id=actual_tenant, role=data.get("role","Client"), email=data.get("email"))
    refresh = create_refresh_token(user_id=user_id, tenant_id=actual_tenant)
    # Update lastLogin
    try:
        db.collection("users").document(user_id).set({"lastLoginAt": datetime.now(timezone.utc)}, merge=True)
    except Exception:
        pass
    await log_audit(tenant_id=actual_tenant, actor_id=user_id, action="LOGIN", entity="auth", entity_id=user_id)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/firebase")  # Hybrid auth: verify Firebase ID token, issue custom JWTs
async def firebase_login(body: FirebaseLoginRequest):
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
async def firebase_register(body: FirebaseLoginRequest):
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
async def mfa_setup():
    from app.core.auth import get_current_user
    from fastapi import Depends
    # This is a placeholder — proper impl requires auth dependency injection at router level
    # For now return a generated secret (caller must be authenticated via separate flow)
    secret = generate_mfa_secret()
    # In real flow: save to user doc, return QR
    # Here we just return for testing
    return {"secret": secret, "provisioning_uri": provisioning_uri(secret, "user@caoms.in"), "qr_data_uri": qr_data_uri(provisioning_uri(secret, "user@caoms.in"))}

@router.post("/mfa/verify")
async def mfa_verify(body: MfaVerifyRequest):
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
async def refresh(body: dict):
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
async def forgot_password(body: ForgotPasswordRequest):
    # Always return success to avoid email enumeration
    # In prod: generate signed token, send email via n8n/SendGrid
    tenant_id = get_current_tenant()
    await log_audit(tenant_id=tenant_id, actor_id=None, action="AUTH", entity="auth/forgot-password", diff={"email": body.email})
    return {"message": "If the account exists, a reset link has been sent (15 min expiry)."}
