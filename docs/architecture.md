# CAOMS — Architecture (Multi-Tenant, Seed Firm `aarav-advisors`)

**Mode:** `TENANT_MODE=multi` (seed firm `aarav-advisors`, `asia-south1`) — every Firestore doc has `tenant_id`. Flip to `single` to pin the seed tenant for one-firm pilot runs; no data migration either way.

## System Context

```
[Browser: Firm Admin | Partner | Manager | Article | Paid | Client Portal]
  --TLS 1.3--> [Vercel Edge / GKE Ingress]
  --> [Next.js 14 :3000] --/api/v1--> [FastAPI :8000]
        JWT{tenant_id, role, sub} --> [TenantMiddleware] --> [RBAC require_permission] --> [AuditMiddleware]
        --> [Firestore asia-south1 + GCS asia-south1 + Secret Manager KMS]
        --> [Redis sessions/cache] --> [n8n cron]
  <-- [Prometheus /metrics + Grafana]
```

## Tenant Isolation (3 layers)

1. **Middleware** `ContextVar tenant_id` from JWT claim (`Authorization: Bearer`) or `X-Tenant-ID` header; every repo query `.where("tenant_id","==",tid)`. `single` mode pins `aarav-advisors`.
   - CORS `OPTIONS` preflight bypasses the tenant check so browsers can negotiate cross-origin calls.
   - `/api/v1/auth/*` in `multi` mode resolves to the seed tenant so a firm can authenticate before identity resolution.
2. **Firestore Rules** `allow read, write: if resource.data.tenant_id == request.auth.token.tenant_id` + `auditLogs: allow update, delete: if false`.
3. **App-level** `require_permission(entity, action)` on every route — never only UI.

## Bounded Contexts

| Context | Firestore collection | Key fields |
|---|---|---|
| Identity | `tenants`, `users`, `sessions` | `tenant_id`, `role`, `password_hash` (bcrypt), `mfaSecretEnc` |
| Client | `clients`, `clients/{id}/contacts` | `pan` unique per tenant via transaction, `aadhaarEnc` (KMS), `gstin` |
| Task | `tasks`, `task_comments`, `task_attachments` | `status` state machine, `overdue` computed, `recurrence` |
| Compliance | `complianceTypes` (global), `complianceDueDates`, `complianceFilings` | `GSTR1, GSTR3B, GSTR9, ITR, TDS, ROC` |
| Document | `documentFolders` (7 per client), `documents`, `documentVersions` | `gcsPath`, `version`, `shareExpiry` |
| Billing | `invoices`, `invoices/{id}/payments` | `INV-FY-XXXX`, `sacCode`, `gstBreakup{cgst,sgst,igst}` |
| Vault | `credentials`, `credentialAccessLogs` | `usernameEnc, passwordEnc` (KMS), reveal logged |
| Audit | `auditLogs` | append-only, `REVOKE UPDATE/DELETE` equivalent via Rules |

## Request Flow

`FE POST /api/v1/clients {JWT tenant_id}` → `TenantMiddleware` resolves `aarav-advisors` → `RBAC` checks `clients:create` → `Firestore transaction` checks duplicate PAN → `GCS` if docs → `auditLogs` append → `201 {client}`.

## Auth + MFA

`bcrypt(12)` → `login` checks password → if `mfaEnabled` returns `{mfa_required, temp_token(5m)}` → `POST /auth/mfa/verify {temp_token, code}` verifies `pyotp` → issues `access(8h)+refresh(7d)` httpOnly cookies + Redis denylist. `forgot-password` signed token 15m via audit log + email (n8n).

## Firebase Auth (Hybrid)

Optional Google Firebase Authentication. When configured it runs **alongside** the legacy email/password flow:

1. Frontend signs in via the Firebase JS SDK (`signInWithEmailAndPassword` or Google Popup) and sends the resulting ID token to `POST /api/v1/auth/firebase`.
2. Backend verifies the token with the Admin SDK (`verify_id_token`) and issues the **same custom JWT** (`access 8h + refresh 7d`) the rest of the app already uses — no changes to the dashboard/sidebar/API layers.
3. If the Firebase email already maps to a local `users` doc, the existing `role` is preserved. If not and `FIREBASE_AUTO_PROVISION=true`, a `Client`-role account is auto-created (and an explicit `/firebase/register` endpoint creates an account awaiting approval).
4. Legacy `POST /api/v1/auth/login` remains active as a fallback — login pages prefer Firebase only when `NEXT_PUBLIC_FIREBASE_*` are set, otherwise they fall back to the legacy flow.

Firebase needs **no** rule changes — `firestore.rules` still keys off `request.auth.token.tenant_id`, and the API writes via the Admin SDK (bypasses client rules).

## Local Dev Env Wiring

Both processes share a single repo-root `.env`:
- **API** — pydantic-settings `_ENV_FILES` resolves `Path(__file__).parents[4] / ".env"` (`apps/api/app/core/config.py`), so `uvicorn` launched from `apps/api` still sees the root env.
- **Web** — `apps/web/.env` is a gitignored symlink to `../../.env`; Next.js loads it from its project root and inlines `NEXT_PUBLIC_*` at build time.

## Non-Functional

- p95 <500ms via `tenantStats` aggregation (cron → `tenantStats/{tenantId}`) + Redis 60s cache, cursor pagination 20, composite indexes `(tenant_id, status, dueDate)`, `(tenant_id, pan)`.
- Dashboard <3s: single-doc read from `tenantStats`.
- 99.9%: GKE HPA, liveness/readiness probes, Firestore regional SLA.
- Backup: Firestore export to GCS daily, PITR enabled.

## Expansion

Add `tenants/{newSlug}` → users with new `tenant_id` → `TENANT_MODE=multi` + wildcard `*.caoms.in`. Existing data stays under `aarav-advisors`.
