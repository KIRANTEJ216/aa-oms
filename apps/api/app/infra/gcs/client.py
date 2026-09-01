import os
import base64
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta

# In-memory GCS stub for dev/local — in prod, swap with google.cloud.storage
# Files stored under /tmp/caoms_gcs/{bucket}/{path} with metadata sidecar

GCS_ROOT = Path(os.getenv("CAOMS_GCS_ROOT", "/tmp/caoms_gcs"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "caoms-docs-dev")


def _safe_path(key: str) -> Path:
    """Resolve a safe on-disk path for the given object key."""
    p = (GCS_ROOT / GCS_BUCKET / key).resolve()
    # Prevent path traversal
    base = (GCS_ROOT / GCS_BUCKET).resolve()
    if not str(p).startswith(str(base)):
        raise ValueError("Invalid object key")
    return p


def upload_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    """Upload bytes to GCS (stub: write to local FS)."""
    p = _safe_path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    # Sidecar metadata
    meta = p.with_suffix(p.suffix + ".meta.json")
    import json
    meta.write_text(json.dumps({
        "key": key,
        "size": len(data),
        "content_type": content_type,
        "md5": hashlib.md5(data).hexdigest(),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }, default=str))
    return {
        "key": key,
        "size": len(data),
        "content_type": content_type,
        "md5": hashlib.md5(data).hexdigest(),
    }


def download_object(key: str) -> bytes:
    """Download bytes from GCS (stub: read from local FS)."""
    p = _safe_path(key)
    if not p.exists():
        raise FileNotFoundError(f"Object not found: {key}")
    return p.read_bytes()


def delete_object(key: str) -> bool:
    p = _safe_path(key)
    if p.exists():
        p.unlink()
    meta = p.with_suffix(p.suffix + ".meta.json")
    if meta.exists():
        meta.unlink()
    return True


def generate_signed_url(key: str, expiry_minutes: int = 5) -> str:
    """Generate a time-limited signed URL for download (stub: returns a base64 token URL)."""
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)).isoformat()
    # In real GCS, this would be storage.Client().bucket(...).blob(...).generate_signed_url(...)
    # For dev: include the expiry + key in a query string the API can verify
    return f"/api/v1/documents/download?key={key}&exp={expires}&sig={token}"


def verify_signed_url(key: str, expires: str, sig: str) -> bool:
    """Verify a signed URL hasn't expired."""
    # URL decode may turn '+00:00' into ' 00:00' — handle both
    expires = expires.replace(" ", "+")
    try:
        exp_dt = datetime.fromisoformat(expires)
    except Exception:
        return False
    return datetime.now(timezone.utc) < exp_dt
