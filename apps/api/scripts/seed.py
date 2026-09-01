"""Seed the seed tenant + demo users + compliance types.

Seed user credentials are NOT hardcoded in this repo. Provide them via env vars:

    SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD
    SEED_PARTNER_EMAIL / SEED_PARTNER_PASSWORD
    SEED_MANAGER_EMAIL / SEED_MANAGER_PASSWORD
    SEED_ARTICLE_EMAIL / SEED_ARTICLE_PASSWORD
    SEED_PAID_EMAIL / SEED_PAID_PASSWORD
    SEED_CLIENT_EMAIL / SEED_CLIENT_PASSWORD

If an email is missing, that user is skipped with a warning. If a password is
missing, a random one is generated and printed to the console.
"""
import os, sys
import secrets
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import datetime, timezone
import uuid
from app.core.security import hash_password
from app.infra.firestore.client import get_db

# role -> (env suffix prefix, display name)
# env vars looked up as: SEED_<PREFIX>_EMAIL / SEED_<PREFIX>_PASSWORD
USER_CONFIG = [
    ("ADMIN", "Firm Admin", "Aarav Advisors Admin"),
    ("PARTNER", "Partner", "Partner"),
    ("MANAGER", "Manager", "Manager"),
    ("ARTICLE", "Article Assistant", "Article"),
    ("PAID", "Paid Assistant", "Paid Assistant"),
    ("CLIENT", "Client", "Demo Client"),
]


def _seed_user(db, tenant_slug, email, role, password, name):
    uid = str(uuid.uuid4())
    # avoid duplicate by email
    existing = list(db.collection("users").where("tenant_id", "==", tenant_slug).where("email", "==", email).limit(1).stream())
    if existing:
        print(f"Skip existing: {email}")
        return
    existing2 = list(db.collection("users").where("email", "==", email).limit(1).stream())
    if existing2:
        print(f"Skip existing (global): {email}")
        return
    db.collection("users").document(uid).set({
        "tenant_id": tenant_slug, "name": name, "email": email, "password_hash": hash_password(password),
        "role": role, "mobile": "+91 98765 43210", "mfaEnabled": False, "mfaSecretEnc": None,
        "isActive": True, "createdAt": datetime.now(timezone.utc), "lastLoginAt": None,
    })
    print(f"Seeded user: {email} / {role}")


def seed():
    db = get_db()
    tenant_slug = os.getenv("SEED_TENANT_SLUG", "aarav-advisors")
    tenant_name = os.getenv("SEED_TENANT_NAME", "Aarav Advisors")

    # Tenant
    db.collection("tenants").document(tenant_slug).set({
        "slug": tenant_slug, "name": tenant_name, "branding": {"logoUrl": None, "primaryColor": "#0F172A"},
        "createdAt": datetime.now(timezone.utc),
    })
    print(f"Seeded tenant: {tenant_slug}")

    for prefix, role, name in USER_CONFIG:
        email = os.getenv(f"SEED_{prefix}_EMAIL", "").strip()
        if not email:
            print(f"WARN: no SEED_{prefix}_EMAIL set — skipping {role}")
            continue
        password = os.getenv(f"SEED_{prefix}_PASSWORD")
        if not password:
            password = secrets.token_urlsafe(12)
            print(f"NOTE: generated random password for {email} ({role}): {password}")
        _seed_user(db, tenant_slug, email, role, password, name)

    # Compliance types (global)
    compliance = [
        ("GSTR1", "GSTR-1 (Monthly)", "Monthly", "11th of following month"),
        ("GSTR3B", "GSTR-3B Monthly return & payment", "Monthly", "20th of following month"),
        ("GSTR9", "GSTR-9 / 9C Annual", "Annual", "31st December"),
        ("ITR_NON_AUDIT", "ITR Individual/HUF (non-audit)", "Annual", "31st July"),
        ("ITR_AUDIT", "ITR Company/Audit Cases", "Annual", "31st October"),
        ("TDS_26Q", "TDS Return 26Q/24Q", "Quarterly", "31st of following month"),
        ("ADV_TAX", "Advance Tax Instalment", "Quarterly", "15th Jun/Sep/Dec/Mar"),
        ("ROC_MGT7", "ROC Annual Return MGT-7", "Annual", "60 days from AGM"),
        ("ROC_AOC4", "Financial Statements AOC-4", "Annual", "30 days from AGM"),
    ]
    for code, name, freq, due in compliance:
        db.collection("complianceTypes").document(code).set({"code": code, "name": name, "frequency": freq, "standardDueDate": due})
    print("Seeded complianceTypes")

    print("Seed complete.")


if __name__ == "__main__":
    seed()