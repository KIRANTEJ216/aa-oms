const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type FetchOpts = RequestInit & { tenantId?: string; raw?: boolean };

export async function apiFetch(path: string, opts: FetchOpts = {}) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((opts.headers as Record<string, string>) || {}),
  };
  const tenant = opts.tenantId || "aarav-advisors";
  if (tenant) headers["X-Tenant-ID"] = tenant;
  const token = typeof window !== "undefined" ? localStorage.getItem("caoms_access_token") : null;
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...opts, headers, credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : `API ${res.status} at ${path}`);
  }
  if (opts.raw) return res;
  return res.json();
}

// ── Types ────────────────────────────────────────────────────────
export type Client = {
  id: string; tenant_id: string; type: string; name: string; pan: string;
  gstin?: string; tan?: string; cin?: string; llpin?: string;
  email: string; mobile: string; address: string;
  engagement_manager: string; services: string[]; is_portal_enabled: boolean;
  dob_or_incorporation: string; created_at: string; updated_at?: string;
};

export type Task = {
  id: string; tenant_id: string; type: string; title: string; description: string;
  priority: "High" | "Medium" | "Low";
  status: "Not Started" | "In Progress" | "Pending Information" | "Under Review" | "Completed" | "Overdue";
  due_date: string; assignee_id?: string; client_id?: string;
  reminder_days: number[]; recurrence_pattern?: string; recurrence_end_condition?: string;
  created_at: string; updated_at?: string; is_overdue: boolean;
};

export type TaskStats = {
  total: number; by_status: Record<string, number>; by_priority: Record<string, number>;
  overdue: number; due_today: number; due_this_week: number;
};

export type ComplianceType = { code: string; name: string; frequency: string; standardDueDate: string };
export type ComplianceFiling = {
  id: string; tenant_id: string; client_id: string; client_name?: string;
  compliance_code: string; compliance_name?: string; period: string;
  actual_due_date: string; status: string; health: "Green" | "Amber" | "Red";
  filed_at?: string; acknowledgement_ref?: string; notes?: string;
  created_at: string; updated_at?: string;
};
export type ComplianceHealth = {
  total: number; by_health: { Green: number; Amber: number; Red: number };
  by_code: Record<string, number>;
  upcoming: Array<{ id: string; compliance_code: string; period: string; actual_due_date: string; health: string; client_id: string; days_until_due: number }>;
};

export type DocFolder = { id: string; name: string; parent_id?: string; path: string; client_id?: string };
export type DocumentItem = {
  id: string; tenant_id: string; client_id: string; folder_id: string; name: string;
  size: number; content_type: string; tags: string[]; version: number; gcs_key: string;
  is_shared: boolean; share_mode?: string; share_expiry?: string;
  uploaded_by?: string; created_at: string; updated_at?: string;
};
export type DocumentVersion = { version: number; size: number; uploaded_by?: string; uploaded_at: string; notes?: string };
export type DocumentShare = { id: string; document_id: string; mode: string; expiry: string; share_url: string };

export type Credential = {
  id: string; tenant_id: string; client_id?: string; name: string;
  url?: string; username_masked: string; notes?: string;
  created_at: string; updated_at?: string; last_accessed_at?: string; access_count: number;
};
export type CredentialReveal = {
  id: string; name: string; username: string; password: string;
  url?: string; notes?: string; revealed_at: string;
};
export type AccessLog = {
  id: string; credential_id: string; credential_name: string;
  actor_id: string; action: string; ip?: string; accessed_at: string;
};

export type InvoiceItem = { description: string; sac_code: string; amount: number; gst_rate: number };
export type Invoice = {
  id: string; invoice_number: string; client_id: string; invoice_type: string;
  gst_treatment: string; gst_breakup: { cgst?: number; sgst?: number; igst?: number };
  items?: InvoiceItem[]; total: number; due_date: string; status: string; created_at: string;
};
export type Payment = { id: string; invoice_id: string; amount: number; payment_method: string; payment_date: string; status: string };
export type AgingReport = { buckets: Record<string, number>; total: number };

export type AuditEntry = {
  id: string; actorId?: string | null; action?: string | null; entity?: string | null;
  entityId?: string | null; method?: string | null; path?: string | null; ip?: string | null;
  userAgent?: string | null; statusCode?: number | null; createdAt?: string | null;
};

// ── API modules ─────────────────────────────────────────────────
export const ClientsAPI = {
  list: () => apiFetch("/api/v1/clients/") as Promise<Client[]>,
  get: (id: string) => apiFetch(`/api/v1/clients/${id}`) as Promise<Client>,
  create: (data: Partial<Client>) => apiFetch("/api/v1/clients/", { method: "POST", body: JSON.stringify(data) }) as Promise<Client>,
  update: (id: string, data: Partial<Client>) => apiFetch(`/api/v1/clients/${id}`, { method: "PATCH", body: JSON.stringify(data) }) as Promise<Client>,
  remove: (id: string) => apiFetch(`/api/v1/clients/${id}`, { method: "DELETE" }) as Promise<{ message: string }>,
};

export const TasksAPI = {
  list: (params?: { status?: string; overdue_only?: boolean; client_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.overdue_only) q.set("overdue_only", "true");
    if (params?.client_id) q.set("client_id", params.client_id);
    const qs = q.toString();
    return apiFetch(`/api/v1/tasks/${qs ? "?" + qs : ""}`) as Promise<Task[]>;
  },
  get: (id: string) => apiFetch(`/api/v1/tasks/${id}`) as Promise<Task>,
  create: (data: Partial<Task>) => apiFetch("/api/v1/tasks/", { method: "POST", body: JSON.stringify(data) }) as Promise<Task>,
  update: (id: string, data: Partial<Task>) => apiFetch(`/api/v1/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }) as Promise<Task>,
  updateStatus: (id: string, status: string, note?: string) =>
    apiFetch(`/api/v1/tasks/${id}/status`, { method: "PATCH", body: JSON.stringify({ status, note }) }) as Promise<Task>,
  remove: (id: string) => apiFetch(`/api/v1/tasks/${id}`, { method: "DELETE" }) as Promise<{ message: string }>,
  stats: () => apiFetch("/api/v1/tasks/stats/summary") as Promise<TaskStats>,
};

export const ComplianceAPI = {
  types: () => apiFetch("/api/v1/compliance/types") as Promise<ComplianceType[]>,
  calendar: (params?: { period?: string; health?: string }) => {
    const q = new URLSearchParams();
    if (params?.period) q.set("period", params.period);
    if (params?.health) q.set("health", params.health);
    const qs = q.toString();
    return apiFetch(`/api/v1/compliance/calendar${qs ? "?" + qs : ""}`) as Promise<ComplianceFiling[]>;
  },
  health: () => apiFetch("/api/v1/compliance/health") as Promise<ComplianceHealth>,
  checklist: (code: string) => apiFetch(`/api/v1/compliance/checklist/${code}`) as Promise<{ code: string; name: string; frequency: string; due_rule: string; items: string[] }>,
  createFiling: (data: { client_id: string; compliance_code: string; period: string; actual_due_date: string; notes?: string }) =>
    apiFetch("/api/v1/compliance/filings", { method: "POST", body: JSON.stringify(data) }) as Promise<ComplianceFiling>,
  updateFiling: (id: string, data: Partial<ComplianceFiling>) =>
    apiFetch(`/api/v1/compliance/filings/${id}`, { method: "PATCH", body: JSON.stringify(data) }) as Promise<ComplianceFiling>,
};

export const DocumentsAPI = {
  folders: (clientId: string) => apiFetch(`/api/v1/documents/folders/${clientId}`) as Promise<DocFolder[]>,
  createFolder: (clientId: string, name: string, parentId?: string) =>
    apiFetch(`/api/v1/documents/folders/${clientId}`, { method: "POST", body: JSON.stringify({ name, parent_id: parentId }) }) as Promise<DocFolder>,
  listByClient: (clientId: string, folderId?: string) => {
    const q = folderId ? `?folder_id=${folderId}` : "";
    return apiFetch(`/api/v1/documents/by-client/${clientId}${q}`) as Promise<DocumentItem[]>;
  },
  upload: (data: { client_id: string; folder_id: string; name: string; content_base64: string; content_type?: string; tags?: string[]; notes?: string }) =>
    apiFetch("/api/v1/documents/upload", { method: "POST", body: JSON.stringify(data) }) as Promise<DocumentItem>,
  versions: (docId: string) => apiFetch(`/api/v1/documents/${docId}/versions`) as Promise<DocumentVersion[]>,
  uploadVersion: (docId: string, content_base64: string, content_type = "application/octet-stream", notes?: string) =>
    apiFetch(`/api/v1/documents/${docId}/version`, { method: "POST", body: JSON.stringify({ content_base64, content_type, notes }) }) as Promise<DocumentVersion>,
  update: (docId: string, data: Partial<DocumentItem>) =>
    apiFetch(`/api/v1/documents/${docId}`, { method: "PATCH", body: JSON.stringify(data) }) as Promise<DocumentItem>,
  remove: (docId: string) => apiFetch(`/api/v1/documents/${docId}`, { method: "DELETE" }) as Promise<{ message: string }>,
  share: (docId: string, mode: "View Only" | "Download Enabled", expiry_days = 7) =>
    apiFetch(`/api/v1/documents/${docId}/share`, { method: "POST", body: JSON.stringify({ mode, expiry_days }) }) as Promise<DocumentShare>,
};

export const CredentialsAPI = {
  list: (clientId?: string) => {
    const q = clientId ? `?client_id=${clientId}` : "";
    return apiFetch(`/api/v1/credentials/${q}`) as Promise<Credential[]>;
  },
  create: (data: { name: string; client_id?: string; url?: string; username: string; password: string; notes?: string }) =>
    apiFetch("/api/v1/credentials/", { method: "POST", body: JSON.stringify(data) }) as Promise<Credential>,
  update: (id: string, data: { name?: string; url?: string; username?: string; password?: string; notes?: string }) =>
    apiFetch(`/api/v1/credentials/${id}`, { method: "PATCH", body: JSON.stringify(data) }) as Promise<Credential>,
  remove: (id: string) => apiFetch(`/api/v1/credentials/${id}`, { method: "DELETE" }) as Promise<{ message: string }>,
  reveal: (id: string) => apiFetch(`/api/v1/credentials/${id}/reveal`, { method: "POST" }) as Promise<CredentialReveal>,
  accessLogs: (credentialId?: string) => {
    const q = credentialId ? `?credential_id=${credentialId}` : "";
    return apiFetch(`/api/v1/credentials/access-logs${q}`) as Promise<AccessLog[]>;
  },
};

// Helper: file to base64 (browser)
export async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the "data:...;base64," prefix
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export const BillingAPI = {
  list: (params?: { status?: string; client_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.client_id) q.set("client_id", params.client_id);
    const qs = q.toString();
    return apiFetch(`/api/v1/billing/invoices${qs ? "?" + qs : ""}`) as Promise<Invoice[]>;
  },
  get: (id: string) => apiFetch(`/api/v1/billing/invoices/${id}`) as Promise<Invoice>,
  create: (data: { client_id: string; invoice_type?: string; items: InvoiceItem[]; due_days?: number; gst_treatment?: string }) =>
    apiFetch("/api/v1/billing/invoices", { method: "POST", body: JSON.stringify(data) }) as Promise<Invoice>,
  recordPayment: (invoiceId: string, data: { amount: number; payment_method?: string }) =>
    apiFetch(`/api/v1/billing/invoices/${invoiceId}/payments`, { method: "POST", body: JSON.stringify(data) }) as Promise<Payment>,
  aging: () => apiFetch("/api/v1/billing/invoices/aging") as Promise<AgingReport>,
};

export const AuditAPI = {
  list: (params?: { limit?: number; entity?: string; action?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.entity) q.set("entity", params.entity);
    if (params?.action) q.set("action", params.action);
    const qs = q.toString();
    return apiFetch(`/api/v1/audit/logs${qs ? "?" + qs : ""}`) as Promise<{ total: number; items: AuditEntry[] }>;
  },
};
