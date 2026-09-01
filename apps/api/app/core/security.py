import bcrypt
import pyotp
import qrcode
import io
import base64
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.core.config import get_settings

def hash_password(plain: str) -> str:
    # bcrypt 4.0.1 — hashpw expects bytes
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(plain.encode(), salt).decode()

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

# ── JWT ──────────────────────────────────────────────────────────
def create_access_token(*, user_id: str, tenant_id: str, role: str, email: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=s.jwt_access_ttl_min)
    payload = {"sub": user_id, "tenant_id": tenant_id, "role": role, "email": email, "iat": int(now.timestamp()), "exp": int(exp.timestamp()), "type": "access"}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)

def create_refresh_token(*, user_id: str, tenant_id: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=s.jwt_refresh_ttl_days)
    payload = {"sub": user_id, "tenant_id": tenant_id, "iat": int(now.timestamp()), "exp": int(exp.timestamp()), "type": "refresh"}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)

def create_temp_token(*, user_id: str, tenant_id: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=5)
    payload = {"sub": user_id, "tenant_id": tenant_id, "iat": int(now.timestamp()), "exp": int(exp.timestamp()), "type": "temp"}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)

def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])

# ── TOTP ─────────────────────────────────────────────────────────
def generate_mfa_secret() -> str:
    return pyotp.random_base32()

def get_totp(secret: str) -> pyotp.TOTP:
    return pyotp.TOTP(secret)

def verify_totp(secret: str, code: str) -> bool:
    return get_totp(secret).verify(code, valid_window=1)

def provisioning_uri(secret: str, email: str) -> str:
    return get_totp(secret).provisioning_uri(name=email, issuer_name="CAOMS")

def qr_data_uri(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
