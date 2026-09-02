"""
Tenant-Scoped GCS Client:
- All object keys automatically prefixed with tenant_id
- Supports both Google Cloud Storage (prod) and local filesystem (dev)
- Signed URL generation and verification
- Metadata management
"""
import os
import base64
import hashlib
import secrets
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, BinaryIO
from app.core.config import get_settings
from app.core.tenant import get_current_tenant

# ============================================================
# Configuration
# ============================================================

GCS_ROOT = Path(os.getenv("CAOMS_GCS_ROOT", "/tmp/caoms_gcs"))
DEFAULT_BUCKET = os.getenv("GCS_BUCKET", "caoms-docs-dev")

# Try to import Google Cloud Storage
try:
    from google.cloud import storage
    HAS_GCS = True
except ImportError:
    HAS_GCS = False


class TenantGCS:
    """
    Tenant-scoped Google Cloud Storage wrapper.
    All operations are automatically scoped to the current tenant.
    """
    
    def __init__(self, bucket: str = None):
        self.bucket_name = bucket or DEFAULT_BUCKET
        self._client = None
        self._bucket = None
        
        if HAS_GCS:
            try:
                self._client = storage.Client()
                self._bucket = self._client.bucket(self.bucket_name)
            except Exception as e:
                print(f"[gcs] GCS unavailable, using local FS: {e}")
    
    def _get_tenant_id(self) -> str:
        """Get current tenant ID, fallback to 'global' if not available."""
        try:
            return get_current_tenant()
        except Exception:
            return "global"
    
    def _tenant_key(self, key: str) -> str:
        """Add tenant prefix to object key."""
        tenant_id = self._get_tenant_id()
        return f"tenants/{tenant_id}/{key}"
    
    def _local_path(self, key: str) -> Path:
        """Get local filesystem path for tenant-scoped key."""
        tenant_key = self._tenant_key(key)
        p = (GCS_ROOT / self.bucket_name / tenant_key).resolve()
        base = (GCS_ROOT / self.bucket_name).resolve()
        if not str(p).startswith(str(base)):
            raise ValueError("Invalid object key")
        return p
    
    # ============================================================
    # Core Operations
    # ============================================================
    
    def upload_object(
        self, 
        key: str, 
        data: bytes, 
        content_type: str = "application/octet-stream",
        metadata: dict = None
    ) -> dict:
        """
        Upload bytes to tenant-scoped storage.
        Returns metadata dict.
        """
        tenant_key = self._tenant_key(key)
        md5_hash = hashlib.md5(data).hexdigest()
        uploaded_at = datetime.now(timezone.utc).isoformat()
        
        meta = {
            "key": tenant_key,
            "original_key": key,
            "tenant_id": self._get_tenant_id(),
            "size": len(data),
            "content_type": content_type,
            "md5": md5_hash,
            "uploaded_at": uploaded_at,
            "metadata": metadata or {},
        }
        
        if self._bucket:
            # Production: Google Cloud Storage
            blob = self._bucket.blob(tenant_key)
            blob.upload_from_string(data, content_type=content_type)
            if metadata:
                blob.metadata = metadata
            blob.patch()
        else:
            # Development: Local filesystem
            p = self._local_path(key)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            meta_file = p.with_suffix(p.suffix + ".meta.json")
            meta_file.write_text(json.dumps(meta, default=str))
        
        return meta
    
    def upload_file(
        self, 
        key: str, 
        file_path: str, 
        content_type: str = None,
        metadata: dict = None
    ) -> dict:
        """Upload a local file to tenant-scoped storage."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if content_type is None:
            import mimetypes
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = "application/octet-stream"
        
        data = p.read_bytes()
        return self.upload_object(key, data, content_type, metadata)
    
    def download_object(self, key: str) -> bytes:
        """Download bytes from tenant-scoped storage."""
        tenant_key = self._tenant_key(key)
        
        if self._bucket:
            blob = self._bucket.blob(tenant_key)
            if not blob.exists():
                raise FileNotFoundError(f"Object not found: {key}")
            return blob.download_as_bytes()
        else:
            p = self._local_path(key)
            if not p.exists():
                raise FileNotFoundError(f"Object not found: {key}")
            return p.read_bytes()
    
    def download_to_file(self, key: str, destination: str) -> None:
        """Download object to local file."""
        data = self.download_object(key)
        Path(destination).write_bytes(data)
    
    def delete_object(self, key: str) -> bool:
        """Delete object from tenant-scoped storage."""
        tenant_key = self._tenant_key(key)
        
        if self._bucket:
            blob = self._bucket.blob(tenant_key)
            if blob.exists():
                blob.delete()
        else:
            p = self._local_path(key)
            if p.exists():
                p.unlink()
            meta = p.with_suffix(p.suffix + ".meta.json")
            if meta.exists():
                meta.unlink()
        return True
    
    def get_metadata(self, key: str) -> dict:
        """Get object metadata."""
        tenant_key = self._tenant_key(key)
        
        if self._bucket:
            blob = self._bucket.blob(tenant_key)
            if not blob.exists():
                raise FileNotFoundError(f"Object not found: {key}")
            blob.reload()
            return {
                "key": key,
                "tenant_key": tenant_key,
                "size": blob.size,
                "content_type": blob.content_type,
                "md5": blob.md5_hash,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "metadata": blob.metadata or {},
            }
        else:
            p = self._local_path(key)
            if not p.exists():
                raise FileNotFoundError(f"Object not found: {key}")
            meta_file = p.with_suffix(p.suffix + ".meta.json")
            if meta_file.exists():
                return json.loads(meta_file.read_text())
            return {"key": key, "tenant_key": tenant_key, "size": p.stat().st_size}
    
    def list_objects(self, prefix: str = "", delimiter: str = None) -> list:
        """List objects in tenant-scoped prefix."""
        tenant_prefix = self._tenant_key(prefix)
        
        if self._bucket:
            blobs = self._bucket.list_blobs(prefix=tenant_prefix, delimiter=delimiter)
            return [
                {
                    "key": blob.name[len("tenants/" + self._get_tenant_id() + "/"):],
                    "tenant_key": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_type,
                    "md5": blob.md5_hash,
                    "created": blob.time_created.isoformat() if blob.time_created else None,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                }
                for blob in blobs
            ]
        else:
            base = self._local_path(prefix)
            if not base.exists():
                return []
            
            results = []
            for p in base.rglob("*"):
                if p.is_file() and not p.name.endswith(".meta.json"):
                    rel_key = str(p.relative_to(GCS_ROOT / self.bucket_name))
                    # Strip tenant prefix
                    tenant_prefix_str = f"tenants/{self._get_tenant_id()}/"
                    if rel_key.startswith(tenant_prefix_str):
                        rel_key = rel_key[len(tenant_prefix_str):]
                    results.append({
                        "key": rel_key,
                        "tenant_key": str(p.relative_to(GCS_ROOT / self.bucket_name)),
                        "size": p.stat().st_size,
                    })
            return results
    
    # ============================================================
    # Signed URLs
    # ============================================================
    
    def generate_signed_url(
        self, 
        key: str, 
        expiry_minutes: int = 5, 
        method: str = "GET",
        content_type: str = None
    ) -> str:
        """
        Generate a time-limited signed URL for tenant-scoped object.
        In production, uses GCS signed URLs.
        In development, returns a token-based URL.
        """
        tenant_key = self._tenant_key(key)
        expires = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
        
        if self._bucket and HAS_GCS:
            # Production: GCS signed URL
            blob = self._bucket.blob(tenant_key)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiry_minutes),
                method=method,
                content_type=content_type,
            )
            return url
        else:
            # Development: Token-based URL
            token = secrets.token_urlsafe(32)
            expires_iso = expires.isoformat()
            return f"/api/v1/documents/download?key={tenant_key}&exp={expires_iso}&sig={token}&method={method}"
    
    def verify_signed_url(self, key: str, expires: str, sig: str, method: str = "GET") -> bool:
        """Verify a signed URL hasn't expired."""
        expires = expires.replace(" ", "+")
        try:
            exp_dt = datetime.fromisoformat(expires)
        except Exception:
            return False
        return datetime.now(timezone.utc) < exp_dt
    
    # ============================================================
    # Utility
    # ============================================================
    
    def object_exists(self, key: str) -> bool:
        """Check if object exists."""
        tenant_key = self._tenant_key(key)
        if self._bucket:
            return self._bucket.blob(tenant_key).exists()
        else:
            return self._local_path(key).exists()
    
    def get_size(self, key: str) -> int:
        """Get object size in bytes."""
        meta = self.get_metadata(key)
        return meta.get("size", 0)
    
    def copy_object(self, source_key: str, dest_key: str) -> dict:
        """Copy object within tenant scope."""
        source_tenant_key = self._tenant_key(source_key)
        dest_tenant_key = self._tenant_key(dest_key)
        
        if self._bucket:
            source_blob = self._bucket.blob(source_tenant_key)
            dest_blob = self._bucket.blob(dest_tenant_key)
            dest_blob.rewrite(source_blob)
        else:
            data = self.download_object(source_key)
            self.upload_object(dest_key, data)
        
        return self.get_metadata(dest_key)
    
    def move_object(self, source_key: str, dest_key: str) -> dict:
        """Move (copy + delete) object within tenant scope."""
        self.copy_object(source_key, dest_key)
        self.delete_object(source_key)
        return self.get_metadata(dest_key)


# ============================================================
# Convenience Functions (backward compatible)
# ============================================================

def get_gcs_client() -> TenantGCS:
    """Get tenant-scoped GCS client."""
    return TenantGCS()


# Backward compatible functions
def upload_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    """Upload object to current tenant's scope."""
    return get_gcs_client().upload_object(key, data, content_type)


def download_object(key: str) -> bytes:
    """Download object from current tenant's scope."""
    return get_gcs_client().download_object(key)


def delete_object(key: str) -> bool:
    """Delete object from current tenant's scope."""
    return get_gcs_client().delete_object(key)


def generate_signed_url(key: str, expiry_minutes: int = 5) -> str:
    """Generate signed URL for current tenant's object."""
    return get_gcs_client().generate_signed_url(key, expiry_minutes)


def verify_signed_url(key: str, expires: str, sig: str) -> bool:
    """Verify signed URL for current tenant's object."""
    return get_gcs_client().verify_signed_url(key, expires, sig)