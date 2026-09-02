from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

# Monorepo: .env may live at the repo root (aa-oms/.env) or in apps/api/.env
_ENV_FILES = (str(Path(__file__).resolve().parents[4] / ".env"), ".env")

class Settings(BaseSettings):
    app_name: str = "CAOMS API"
    env: str = "development"
    # Tenant
    tenant_mode: str = "single"  # single | multi
    seed_tenant_slug: str = "aarav-advisors"
    seed_tenant_name: str = "Aarav Advisors"
    # Firestore
    google_cloud_project: str = "caoms-dev"
    firestore_location: str = "asia-south1"
    firestore_emulator_host: str = ""  # e.g. localhost:8080
    # GCS
    gcs_bucket: str = "caoms-docs-dev"
    gcs_emulator_host: str = ""  # http://localhost:4443
    # Secrets
    secret_manager_project: str = "caoms-dev"
    jwt_secret: str = "change-me-32-chars-minimum-jwt-secret-dev-only"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_min: int = 480
    jwt_refresh_ttl_days: int = 7
    # Firebase Auth (hybrid: verify Firebase ID tokens, issue custom JWTs)
    firebase_project_id: str = ""
    firebase_client_email: str = ""
    firebase_private_key: str = ""
    firebase_auto_provision: bool = True  # create a Client account on first Firebase login
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_redis_url: str = "redis://localhost:6379/1"
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # n8n Webhook
    n8n_webhook_url: str = ""
    # Security - Auth Hardening
    bcrypt_rounds: int = 12
    password_min_length: int = 12
    password_require_upper: bool = True
    password_require_lower: bool = True
    password_require_digit: bool = True
    password_require_special: bool = True
    password_max_age_days: int = 90
    password_history_count: int = 5
    # Security - Login Protection
    login_max_attempts: int = 5
    login_lockout_duration_min: int = 15
    login_attempt_window_min: int = 15
    # Security - Session Management
    session_max_per_user: int = 5
    session_absolute_timeout_hours: int = 24
    session_idle_timeout_hours: int = 8
    # Security - Email Verification
    email_verification_required: bool = True
    verify_token_ttl_hours: int = 24
    # Security - Password Reset
    reset_token_ttl_min: int = 15
    # Security - Rate Limiting
    rate_limit_per_min: int = 100
    rate_limit_enabled: bool = True
    # Security - Bot Protection
    turnstile_secret: str = ""
    turnstile_site_key: str = ""
    recaptcha_secret: str = ""
    recaptcha_site_key: str = ""
    bot_protection_enabled: bool = True
    # Security - API Keys
    api_key_prefix: str = "caoms_"
    api_key_default_expires_days: int = 365
    # Security - HMAC
    hmac_signature_required_paths: str = "/api/v1/webhooks/"
    hmac_max_timestamp_drift_seconds: int = 300
    # Security - Payload/Timeout
    max_payload_size_mb: int = 10
    request_timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
