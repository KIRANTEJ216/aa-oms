# CAOMS — CA Office Management SaaS

**Multi-tenant CA office management platform.** Current mode: `TENANT_MODE=multi` (seed firm `aarav-advisors`). Every document carries `tenant_id`; tenant resolution and RBAC are enforced at every API layer, never just in the UI.

> **Stack:** Next.js 14 (App Router) + TypeScript + Tailwind + ShadCN · FastAPI + Pydantic v2 + Python 3.11 · Firestore (asia-south1) + GCS + Secret Manager + KMS · Redis · n8n · Docker + GKE · GitHub Actions

---

## Phase Status

| Phase | Name | Status |
|---|---|---|
| 0 | Skeleton & Auth (login, register, JWT, MFA scaffold) | ✅ Done |
| 1 | Multi-Tenant Architecture (`tenant_id` + middleware) | ✅ Done |
| 2 | RBAC Engine (7 roles × 5 perms) | ✅ Done |
| 3 | Client Management (PAN/GSTIN, duplicate detection) | ✅ Done |
| 4 | Task Management (status, escalation, recurrence) | ✅ Done |
| 5 | Compliance (GST/ITR/TDS/ROC, health Green/Amber/Red) | ✅ Done |
| 6 | Document Management (GCS, versioning, 7 folders) | ✅ Done |
| 7 | Credential Vault (KMS AES-256, access logs) | ✅ Done |
| 8 | Billing (INV-FY-XXXX, CGST/SGST vs IGST, aging) | ✅ Done |
| 9 | Audit Trail (immutable) | ✅ Done |
| 10 | Client Portal | 🟡 In Progress |
| 11 | Hardening & GKE (p95 <500ms, <3s dashboard, 99.9%) | ⏳ Pending |

`multi` = per-tenant firm onboarding. `single` = one-firm pilot (pins `tenant_id = aarav-advisors`). Flip back to `single` at any time with zero migration.

---

## Quick Start

```bash
cp .env.example .env
# fill GOOGLE_CLOUD_PROJECT, JWT_SECRET etc. (emulators work with defaults)
docker compose up firestore-emulator redis gcs-emulator -d   # emulators only
pnpm dev                      # runs web + api concurrently via turbo
```

> The API reads the repo-root `.env` (see `apps/api/app/core/config.py`). The web app picks it up via `apps/web/.env -> ../../.env` (symlink, gitignored).

| Service | URL |
|---|---|
| Web (Next.js) | http://localhost:3000 |
| API (FastAPI) | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Firestore Emulator UI | http://localhost:4000 |
| GCS Emulator | http://localhost:4443 |
| Redis | localhost:6379 |
| n8n | http://localhost:5678 |

---

## Environment Variables

See `.env.example`. Key vars:

| Var | Purpose | Default |
|---|---|---|
| `TENANT_MODE` | `multi` (SaaS) or `single` (pilot) | `multi` |
| `SEED_TENANT_SLUG` | seed firm slug | `aarav-advisors` |
| `JWT_ACCESS_TTL_MIN` | access token lifetime (hardcoded default 480 = 8h) | `480` |
| `JWT_REFRESH_TTL_DAYS` | refresh token lifetime | `7` |
| `FIRESTORE_LOCATION` | India residency | `asia-south1` |
| `JWT_SECRET` | HS256 signing | change-me |
| `REDIS_URL` | sessions/cache | `redis://localhost:6379/0` |
| `GCS_BUCKET` | doc storage | `caoms-docs-dev` |

---

## Monorepo

```
/caoms
  /apps/web          Next.js 14 frontend (0.2.0)
  /apps/api          FastAPI backend (0.2.0, Python 3.11)
  /packages/shared   Shared types/validators (0.2.0)
  /infra/docker      Dockerfiles + compose
  /infra/k8s         GKE manifests
  /infra/ci          GitHub Actions
  docs/              architecture, ERD, openapi
```

---

## API

Visit `/docs` (Swagger) while the API is running. Spec committed to `docs/openapi.yaml`.

Auth: `Authorization: Bearer <JWT>` + `X-Tenant-ID: <tenant-slug>` (enforced when `TENANT_MODE=multi`). Access token lives 8h with a 7-day refresh token. CORS `OPTIONS` preflight is exempt from the tenant check.

---

## Security

- Passwords: `bcrypt` (never plaintext)
- MFA: TOTP via `pyotp` (mandatory)
- All traffic TLS 1.3 (GKE ingress)
- Sensitive fields (Aadhaar, credential passwords) encrypted via Secret Manager + KMS, masked `****1234` in APIs
- OWASP Top 10: CORS, CSP, CSRF, rate-limit 100 req/min, parameterized queries only

---

## Multi-tenancy

Every Firestore document has `tenant_id`. Middleware resolves the tenant from JWT claim / `X-Tenant-ID` header / subdomain; every query filters by it. Firestore Rules deny cross-tenant reads; `auditLogs` is append-only. `single` mode pins `tenant_id = SEED_TENANT_ID` so no header spoofing. Auth routes (`/api/v1/auth/*`) resolve to the seed tenant in `multi` mode so a firm can sign in on its own subdomain before its identity is resolved.

---

## Commands

| Command | Purpose |
|---|---|
| `make dev` | `pnpm dev` via turbo |
| `make seed` | seed `aarav-advisors` tenant + demo users |
| `make docker-up` | `docker compose up --build` (emulators) |
| `make lint` / `make test` / `make build` | via turbo |
| `pnpm lint` | ESLint (web) |
| `npx tsc --noEmit` | TypeScript check (web) |

---

## Seed Users

`make seed` creates the `aarav-advisors` tenant plus role users (Firm Admin, Partner, Manager, Article Assistant, Paid Assistant, Client). Emails and passwords are supplied via `SEED_*_EMAIL` / `SEED_*_PASSWORD` env vars (see `apps/api/scripts/seed.py` and `.env.example`) — users without an email are skipped, and missing passwords are auto-generated and printed. No credentials are committed to this repository.

---

## Roadmap

Inline-pilot complete (dashboard, clients, tasks, compliance, documents, vault, billing, audit all live against Firestore). Next: client portal polish, then hardening — p95 `<500ms` via `tenantStats` aggregation + Redis cache, `<3s` dashboard, 99.9% on GKE with HPA + regional Firestore. See `docs/architecture.md`.