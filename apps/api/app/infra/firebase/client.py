"""Firebase Auth (hybrid) — verify Firebase ID tokens via the Admin SDK.

Credentials come from env vars: FIREBASE_CLIENT_EMAIL + FIREBASE_PRIVATE_KEY
(or GOOGLE_APPLICATION_CREDENTIALS / ADC). Lazy init so the emulator/dev
flows work without real Firebase credentials.
"""
from functools import lru_cache
from app.core.config import get_settings


def _is_configured() -> bool:
    s = get_settings()
    return bool(s.firebase_project_id and s.firebase_client_email and s.firebase_private_key)


APP_NAME = "caoms-hybrid"


def _make_credential(s):
    from firebase_admin import credentials

    return credentials.Certificate({
        "type": "service_account",
        "project_id": s.firebase_project_id,
        "private_key": s.firebase_private_key.replace("\\n", "\n"),
        "client_email": s.firebase_client_email,
        "token_uri": "https://oauth2.googleapis.com/token",
    })


@lru_cache
def get_firebase_app():
    """Return the named firebase app (initialized once from env creds), or None.

    Uses a dedicated named app so it never collides with the default app the
    Firestore infra may have already initialized (which on Vercel has no
    credentials). verify_id_token is always pinned to this app.
    """
    s = get_settings()
    if not _is_configured():
        return None
    import firebase_admin

    if APP_NAME not in firebase_admin._apps:
        firebase_admin.initialize_app(_make_credential(s), name=APP_NAME)
    return firebase_admin.get_app(APP_NAME)


def verify_id_token(id_token: str) -> dict:
    app = get_firebase_app()
    if app is None:
        raise RuntimeError("Firebase Auth not configured")
    from firebase_admin import auth

    return auth.verify_id_token(id_token, app=app)