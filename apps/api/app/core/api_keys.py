"""
API Key Management with HMAC Signing and Replay Protection:
- API key generation, validation, rotation, revocation
- HMAC-SHA256 request signing for server-to-server auth
- Timestamp-based replay attack protection
- Per-key scopes/permissions
- Key prefix identification for logging
"""
from fastapi import HTTPException, Header, Request, Depends
from datetime import datetime, timedelta, timezone
import secrets
import hashlib
import hmac
import base64
from typing import Optional, List
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant
from app.core.config import get_settings
from app.core.audit import log_audit

settings = get_settings()

# ============================================================
# Constants
# ============================================================

API_KEY_PREFIX = settings.api_key_prefix  # "caoms_"
KEY_LENGTH = 32
KEY_ID_LENGTH = 16
HASH_ROUNDS = 100000
HMAC_MAX_DRIFT_SECONDS = settings.hmac_max_timestamp_drift_seconds  # 300 seconds (5 min)
DEFAULT_EXPIRES_DAYS = settings.api_key_default_expires_days

# Scopes for API keys
API_KEY_SCOPES = {
    "clients:read", "clients:write",
    "tasks:read", "tasks:write",
    "documents:read", "documents:write",
    "compliance:read", "compliance:write",
    "billing:read", "billing:write",
    "credentials:read", "credentials:write",
    "reports:read", "reports:write",
    "bd:read", "bd:write",
    "support:read", "support:write",
    "audit:read",
    "webhooks:receive",
    "admin:all",
}


# ============================================================
# API Key Manager
# ============================================================

class APIKeyManager:
    """Manages API key lifecycle: create, validate, revoke, rotate."""
    
    @classmethod
    def _generate_raw_key(cls) -> str:
        """Generate a new raw API key with prefix."""
        return API_KEY_PREFIX + secrets.token_urlsafe(KEY_LENGTH)
    
    @classmethod
    def _hash_key(cls, raw_key: str, salt: bytes) -> str:
        """Hash API key with PBKDF2."""
        return hashlib.pbkdf2_hmac('sha256', raw_key.encode(), salt, HASH_ROUNDS).hex()
    
    @classmethod
    def _generate_salt(cls) -> bytes:
        return secrets.token_bytes(16)
    
    @classmethod
    def _get_key_prefix(cls, raw_key: str) -> str:
        """Get identifiable prefix (first 12 chars after prefix)."""
        return raw_key[:len(API_KEY_PREFIX) + 12]
    
    @classmethod
    async def create_key(
        cls,
        name: str,
        tenant_id: str,
        user_id: str,
        scopes: List[str],
        expires_days: int = DEFAULT_EXPIRES_DAYS,
        description: str = ""
    ) -> dict:
        """
        Create a new API key.
        Returns dict with raw_key (only shown once!), key_id, and metadata.
        """
        # Validate scopes
        invalid_scopes = set(scopes) - API_KEY_SCOPES
        if invalid_scopes:
            raise HTTPException(400, f"Invalid scopes: {invalid_scopes}")
        
        raw_key = cls._generate_raw_key()
        salt = cls._generate_salt()
        key_hash = cls._hash_key(raw_key, salt)
        key_prefix = cls._get_key_prefix(raw_key)
        key_id = secrets.token_urlsafe(KEY_ID_LENGTH)
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        
        db = get_db()
        key_doc = {
            "key_id": key_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "name": name,
            "description": description,
            "key_hash": key_hash,
            "salt": salt.hex(),
            "key_prefix": key_prefix,
            "scopes": scopes,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
            "last_used_at": None,
            "last_used_ip": None,
            "revoked": False,
            "revoked_at": None,
            "revoked_reason": None,
        }
        
        db.collection("apiKeys").document(key_id).set(key_doc)
        
        await log_audit(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="API_KEY_CREATE",
            entity="api_keys",
            entity_id=key_id,
            diff={"name": name, "scopes": scopes, "expires_days": expires_days}
        )
        
        # Return raw key ONLY ONCE
        return {
            "key_id": key_id,
            "raw_key": raw_key,
            "name": name,
            "scopes": scopes,
            "expires_at": expires_at.isoformat(),
            "created_at": key_doc["created_at"].isoformat(),
            "warning": "Store this key securely. It will not be shown again."
        }
    
    @classmethod
    async def validate_key(cls, raw_key: str) -> Optional[dict]:
        """
        Validate an API key and return key info if valid.
        Returns None if invalid, expired, or revoked.
        """
        if not raw_key or not raw_key.startswith(API_KEY_PREFIX):
            return None
        
        key_prefix = cls._get_key_prefix(raw_key)
        
        db = get_db()
        # Query by prefix (indexed)
        docs = list(db.collection("apiKeys")
                   .where("key_prefix", "==", key_prefix)
                   .where("revoked", "==", False)
                   .stream())
        
        for doc in docs:
            data = doc.to_dict()
            data["key_id"] = doc.id
            
            # Verify hash
            salt = bytes.fromhex(data.get("salt", ""))
            expected_hash = cls._hash_key(raw_key, salt)
            
            if secrets.compare_digest(data["key_hash"], expected_hash):
                # Check expiry
                expires = data.get("expires_at")
                if expires:
                    if isinstance(expires, str):
                        expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > expires:
                        return None
                
                # Update last used
                db.collection("apiKeys").document(doc.id).update({
                    "last_used_at": datetime.now(timezone.utc),
                })
                
                return data
        
        return None
    
    @classmethod
    async def list_keys(cls, tenant_id: str, user_id: str = None, include_revoked: bool = False) -> List[dict]:
        """List API keys for a tenant (optionally filtered by user)."""
        db = get_db()
        query = db.collection("apiKeys").where("tenant_id", "==", tenant_id)
        
        if user_id:
            query = query.where("user_id", "==", user_id)
        if not include_revoked:
            query = query.where("revoked", "==", False)
        
        docs = list(query.stream())
        keys = []
        for doc in docs:
            data = doc.to_dict()
            data["key_id"] = doc.id
            # Don't expose hash/salt
            data.pop("key_hash", None)
            data.pop("salt", None)
            keys.append(data)
        return keys
    
    @classmethod
    async def revoke_key(cls, key_id: str, tenant_id: str, user_id: str, reason: str = "manual") -> bool:
        """Revoke an API key."""
        db = get_db()
        doc = db.collection("apiKeys").document(key_id).get()
        if not doc.exists:
            return False
        
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            return False
        
        db.collection("apiKeys").document(key_id).update({
            "revoked": True,
            "revoked_at": datetime.now(timezone.utc),
            "revoked_reason": reason,
        })
        
        await log_audit(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="API_KEY_REVOKE",
            entity="api_keys",
            entity_id=key_id,
            diff={"reason": reason, "name": data.get("name")}
        )
        return True
    
    @classmethod
    async def rotate_key(cls, key_id: str, tenant_id: str, user_id: str, 
                        new_expires_days: int = DEFAULT_EXPIRES_DAYS) -> dict:
        """Rotate an API key - revoke old, create new with same scopes."""
        db = get_db()
        doc = db.collection("apiKeys").document(key_id).get()
        if not doc.exists:
            raise HTTPException(404, "API key not found")
        
        data = doc.to_dict()
        if data.get("tenant_id") != tenant_id:
            raise HTTPException(403, "Tenant mismatch")
        
        # Revoke old
        await cls.revoke_key(key_id, tenant_id, user_id, "rotated")
        
        # Create new with same scopes
        return await cls.create_key(
            name=data.get("name", "Rotated Key"),
            tenant_id=tenant_id,
            user_id=user_id,
            scopes=data.get("scopes", []),
            expires_days=new_expires_days,
            description=f"Rotated from {key_id}"
        )
    
    @classmethod
    async def check_scope(cls, key_info: dict, required_scope: str) -> bool:
        """Check if API key has required scope."""
        scopes = key_info.get("scopes", [])
        return required_scope in scopes or "admin:all" in scopes


# ============================================================
# HMAC Request Signing
# ============================================================

class HMACVerifier:
    """Verify HMAC-SHA256 signed requests."""
    
    @staticmethod
    def create_signature(raw_key: str, payload: bytes, timestamp: str) -> str:
        """
        Create HMAC-SHA256 signature.
        Message format: "{timestamp}.{payload}"
        """
        message = f"{timestamp}.{payload.decode('utf-8', errors='ignore')}".encode()
        signature = hmac.new(raw_key.encode(), message, hashlib.sha256).hexdigest()
        return signature
    
    @staticmethod
    def verify_signature(raw_key: str, payload: bytes, timestamp: str, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = HMACVerifier.create_signature(raw_key, payload, timestamp)
        return secrets.compare_digest(expected, signature)
    
    @staticmethod
    def verify_timestamp(timestamp: str) -> bool:
        """Verify timestamp is within allowed drift."""
        try:
            ts = int(timestamp)
            now = datetime.now(timezone.utc).timestamp()
            return abs(now - ts) <= HMAC_MAX_DRIFT_SECONDS
        except (ValueError, TypeError):
            return False


# ============================================================
# Replay Protection (Nonce/Timestamp tracking)
# ============================================================

class ReplayProtection:
    """Track used nonces/timestamps to prevent replay attacks."""
    
    NONCE_TTL_SECONDS = HMAC_MAX_DRIFT_SECONDS * 2  # 10 minutes
    
    @classmethod
    async def check_and_store(cls, key_id: str, timestamp: str, nonce: str = None) -> bool:
        """
        Check if request is a replay.
        Returns True if allowed (not a replay), False if replay detected.
        """
        redis = get_redis()
        
        # Use timestamp + nonce as unique identifier
        if nonce:
            replay_key = f"replay:{key_id}:{timestamp}:{nonce}"
        else:
            replay_key = f"replay:{key_id}:{timestamp}"
        
        # Try to set with NX (only if not exists)
        result = await redis.set(replay_key, "1", nx=True, ex=cls.NONCE_TTL_SECONDS)
        
        if not result:
            # Already exists - replay detected
            await log_audit(
                tenant_id="",  # Will be filled from key info
                actor_id=None,
                action="REPLAY_ATTACK",
                entity="security/hmac",
                diff={"key_id": key_id, "timestamp": timestamp, "nonce": nonce},
            )
            return False
        
        return True


# ============================================================
# FastAPI Dependencies
# ============================================================

async def get_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    x_nonce: Optional[str] = Header(None, alias="X-Nonce"),
    request: Request = None,
) -> dict:
    """
    FastAPI dependency for API key authentication with optional HMAC verification.
    
    Usage:
        @router.get("/data")
        async def get_data(key_info: dict = Depends(get_api_key)):
    
    Headers:
        X-API-Key: caoms_xxxxx... (required)
        X-Signature: <hmac-sha256> (required if HMAC enforced for path)
        X-Timestamp: <unix-timestamp> (required if HMAC)
        X-Nonce: <random-string> (optional, for replay protection)
    """
    if not x_api_key:
        raise HTTPException(401, "API key required (X-API-Key header)")
    
    key_info = await APIKeyManager.validate_key(x_api_key)
    if not key_info:
        raise HTTPException(401, "Invalid or expired API key")
    
    # Check if HMAC is required for this path
    hmac_required_paths = settings.hmac_signature_required_paths.split(",")
    hmac_required = any(request.url.path.startswith(p.strip()) for p in hmac_required_paths if p.strip())
    
    if hmac_required:
        if not x_signature or not x_timestamp:
            raise HTTPException(401, "HMAC signature required (X-Signature, X-Timestamp headers)")
        
        # Verify timestamp
        if not HMACVerifier.verify_timestamp(x_timestamp):
            raise HTTPException(401, "Request timestamp expired or invalid")
        
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify signature
        if not HMACVerifier.verify_signature(x_api_key, body, x_timestamp, x_signature):
            raise HTTPException(401, "Invalid HMAC signature")
        
        # Replay protection
        if not await ReplayProtection.check_and_store(key_info["key_id"], x_timestamp, x_nonce):
            raise HTTPException(401, "Replay attack detected")
    
    return key_info


def require_api_key_scope(required_scope: str):
    """Dependency factory for scope-based API key authorization."""
    async def checker(key_info: dict = Depends(get_api_key)):
        if not await APIKeyManager.check_scope(key_info, required_scope):
            raise HTTPException(403, f"API key missing required scope: {required_scope}")
        return key_info
    return checker


# ============================================================
# Webhook Signature Verification (for n8n, Stripe, etc.)
# ============================================================

class WebhookVerifier:
    """Verify webhook signatures from external services."""
    
    @staticmethod
    def verify_stripe(payload: bytes, signature_header: str, secret: str) -> bool:
        """Verify Stripe webhook signature."""
        try:
            # Stripe format: "t=timestamp,v1=signature"
            parts = signature_header.split(",")
            timestamp = None
            signatures = []
            for part in parts:
                k, v = part.split("=", 1)
                if k == "t":
                    timestamp = v
                elif k == "v1":
                    signatures.append(v)
            
            if not timestamp or not signatures:
                return False
            
            # Verify timestamp
            if not HMACVerifier.verify_timestamp(timestamp):
                return False
            
            # Verify signature
            message = f"{timestamp}.{payload.decode()}".encode()
            expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
            
            for sig in signatures:
                if secrets.compare_digest(sig, expected):
                    return True
            return False
        except Exception:
            return False
    
    @staticmethod
    def verify_github(payload: bytes, signature_header: str, secret: str) -> bool:
        """Verify GitHub webhook signature (sha256=...)."""
        try:
            if not signature_header.startswith("sha256="):
                return False
            sig = signature_header[7:]
            expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            return secrets.compare_digest(sig, expected)
        except Exception:
            return False
    
    @staticmethod
    def verify_generic_hmac(payload: bytes, signature: str, secret: str, timestamp: str = None) -> bool:
        """Verify generic HMAC-SHA256 signature."""
        if timestamp and not HMACVerifier.verify_timestamp(timestamp):
            return False
        
        if timestamp:
            message = f"{timestamp}.{payload.decode()}".encode()
        else:
            message = payload
        
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        return secrets.compare_digest(signature, expected)


# ============================================================
# Helper: Generate API Key for Testing
# ============================================================

def generate_test_api_key() -> str:
    """Generate a test API key (for development only)."""
    return API_KEY_PREFIX + secrets.token_urlsafe(KEY_LENGTH)