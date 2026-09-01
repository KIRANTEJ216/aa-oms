import os
import base64
import hashlib
import hmac
import json
import secrets
from typing import Tuple

# AES-256-GCM via cryptography lib (with Fernet fallback if unavailable)
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _AES_AVAILABLE = True
except ImportError:
    _AES_AVAILABLE = False
    from cryptography.fernet import Fernet  # fallback

# Master key — in dev we use a derived key from JWT_SECRET.
# In prod, this comes from Google Secret Manager / KMS.
_MASTER_KEY_RAW = os.getenv("JWT_SECRET", "change-me-32-chars-minimum-jwt-secret-dev-only")
_MASTER_KEY = hashlib.sha256(_MASTER_KEY_RAW.encode()).digest()  # 32 bytes for AES-256
_AAD = b"caoms-v1"  # additional authenticated data (binds ciphertext to context)


def _aesgcm_encrypt(plaintext: str) -> str:
    """AES-256-GCM encrypt. Output: base64( nonce(12) || ciphertext+tag )."""
    nonce = secrets.token_bytes(12)
    aes = AESGCM(_MASTER_KEY)
    ct = aes.encrypt(nonce, plaintext.encode(), _AAD)
    return base64.b64encode(nonce + ct).decode()


def _aesgcm_decrypt(blob: str) -> str:
    """AES-256-GCM decrypt."""
    data = base64.b64decode(blob.encode())
    nonce, ct = data[:12], data[12:]
    aes = AESGCM(_MASTER_KEY)
    return aes.decrypt(nonce, ct, _AAD).decode()


def encrypt_value(plain: str) -> str:
    """Encrypt a string. Returns a base64 envelope prefixed with 'aes:' so we can detect/upgrade later."""
    if _AES_AVAILABLE:
        return "aes:" + _aesgcm_encrypt(plain)
    # Fallback: Fernet
    f = Fernet(base64.urlsafe_b64encode(_MASTER_KEY))
    return "fer:" + f.encrypt(plain.encode()).decode()


def decrypt_value(enc: str) -> str:
    """Decrypt a string encrypted by encrypt_value()."""
    if not enc:
        return enc
    if enc.startswith("aes:"):
        return _aesgcm_decrypt(enc[4:])
    if enc.startswith("fer:"):
        f = Fernet(base64.urlsafe_b64encode(_MASTER_KEY))
        return f.decrypt(enc[4:].encode()).decode()
    # Legacy / unprefixed — treat as base64-only (backward compat)
    try:
        return base64.b64decode(enc.encode()).decode()
    except Exception:
        return enc


def mask_value(enc: str, last_n: int = 4) -> str:
    """Decrypt and mask for display: ****1234."""
    try:
        plain = decrypt_value(enc)
        if len(plain) >= last_n:
            return "•" * (len(plain) - last_n) + plain[-last_n:]
        return "•" * len(plain)
    except Exception:
        return "••••"


def mask_aadhaar(enc: str) -> str:
    return mask_value(enc, last_n=4)


def field_fingerprint(plain: str) -> str:
    """One-way fingerprint for duplicate detection (e.g., hash of Aadhaar)."""
    return hashlib.sha256(plain.encode()).hexdigest()[:16]


def hmac_sign(secret_key: str, payload: str) -> str:
    """HMAC-SHA256 for signed tokens (e.g., password reset)."""
    return hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def hmac_verify(secret_key: str, payload: str, signature: str) -> bool:
    return hmac.compare_digest(hmac_sign(secret_key, payload), signature)
