from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.core.security import decode_token
from app.infra.firestore.client import get_db
from jose import JWTError, ExpiredSignatureError

bearer = HTTPBearer(auto_error=False)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    # Optional: verify user still active in Firestore (skip if emulator offline)
    try:
        db = get_db()
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            if not data.get("isActive", True):
                raise HTTPException(status_code=403, detail="Account disabled")
            if data.get("tenant_id") != tenant_id:
                raise HTTPException(status_code=401, detail="Tenant mismatch")
    except HTTPException:
        raise
    except Exception:
        # Firestore unavailable (emulator down) — allow token-only auth in dev
        pass
    return {"user_id": user_id, "tenant_id": tenant_id, "role": payload.get("role"), "email": payload.get("email"), "payload": payload}

async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except Exception:
        return None
