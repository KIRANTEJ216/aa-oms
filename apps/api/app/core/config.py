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
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # n8n Webhook
    n8n_webhook_url: str = ""
    # Security
    bcrypt_rounds: int = 12
    rate_limit_per_min: int = 100

    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
