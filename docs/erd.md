# CAOMS — Firestore ERD (tenant_id on every document)

```mermaid
erDiagram
    tenants ||--o{ users : "tenant_id = aarav-advisors (single mode)"
    tenants ||--o{ clients : tenant_id
    tenants ||--o{ tasks : tenant_id
    tenants ||--o{ invoices : tenant_id
    tenants ||--o{ documents : tenant_id
    tenants ||--o{ credentials : tenant_id
    tenants ||--o{ auditLogs : tenant_id
    tenants ||--o{ tenantStats : tenant_id

    users ||--o{ sessions : userId
    clients ||--o{ tasks : clientId
    clients ||--o{ documents : clientId
    clients ||--o{ invoices : clientId
    clients ||--o{ complianceFilings : clientId
    clients ||--o{ credentials : clientId
    complianceTypes ||--o{ complianceDueDates : code
    complianceTypes ||--o{ complianceFilings : code
    documentFolders ||--o{ documents : folderId
    documents ||--o{ documentVersions : docId
    invoices ||--o{ payments : invoiceId
    credentials ||--o{ credentialAccessLogs : credentialId

    tenants { string slug PK "aarav-advisors" string name json branding datetime createdAt }
    users { string id PK string tenant_id FK string email "unique(tenant_id,email)" string password_hash string role "7 roles" boolean mfaEnabled string mfaSecretEnc boolean isActive }
    clients { string id PK string tenant_id string type "Individual/HUF/Company/LLP/Trust" string name string pan "unique(tenant_id,pan) via transaction" string aadhaarEnc "KMS + masked" string gstin string tan string cin string llpin datetime dobOrIncorporation string engagementManagerId string services }
    tasks { string id PK string tenant_id string type string priority string status "incl. Overdue computed" datetime dueDate string assigneeId string clientId }
    complianceTypes { string code PK "GSTR1,GSTR3B,GSTR9,ITR,TDS,ROC" string name string frequency string standardDueDate }
    complianceFilings { string id PK string tenant_id string clientId string code FK "compliance type" string status "pending/due/filed" datetime dueDate datetime filedOn string filedBy string health "Green/Amber/Red" }
    documents { string id PK string tenant_id string clientId string folderId string gcsPath int version bool isShared }
    invoices { string id PK string tenant_id string clientId string invoiceNumber "INV-FY-XXXX" string supplyType "INTRA(cgst+sgst)/INTER(igst)" json gstBreakup }
    credentials { string id PK string tenant_id string name string usernameEnc string passwordEnc }
    auditLogs { string id PK string tenant_id string actorId string action "LOGIN/LOGOUT/CREATE/UPDATE/DELETE/EXPORT/VIEW_CREDENTIAL" string entity datetime createdAt "append-only" }
    tenantStats { string tenantId PK json counters json healthBreakdown datetime updatedAt "dashboard agg via cron + 60s Redis cache" }
```

**Indexes (composite):** `(tenant_id, pan)`, `(tenant_id, gstin)`, `(tenant_id, status, dueDate)`, `(tenant_id, createdAt desc)`.

**Rules:** Every read/write filters `tenant_id == request.auth.token.tenant_id`. `auditLogs` denies update/delete. `single` mode pins `tenant_id`; `multi` resolves from JWT/header. Cross-tenant isolation holds in both.

**Encryption:** `aadhaarEnc`, `usernameEnc`, `passwordEnc` via Secret Manager KMS (dev: base64 stub). Serializers mask `**** + last4`.
