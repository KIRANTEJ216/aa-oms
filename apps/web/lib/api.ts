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
  dob_or_incorporation: string; aadhaar_masked?: string; has_aadhaar?: boolean;
  created_at: string; updated_at?: string;
};
export type ClientPayload = Partial<Omit<Client, "id" | "tenant_id" | "aadhaar_masked" | "has_aadhaar" | "created_at" | "updated_at">> & { aadhaar?: string };

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
  checklist_progress?: Record<string, boolean>;
  checklist_done?: number; checklist_total?: number;
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
  portal?: string; portal_label?: string;
  url?: string; username_masked: string; notes?: string;
  expires_at?: string; days_to_expiry?: number; expiry_status?: "expired" | "expiring_soon" | "ok";
  created_at: string; updated_at?: string; last_accessed_at?: string; access_count: number;
};
export type CredentialReveal = {
  id: string; name: string; portal?: string; username: string; password: string;
  url?: string; notes?: string; expires_at?: string; revealed_at: string;
};
export type PortalInfo = { key: string; label: string; url: string; expiry_hint: string };
export type ClientChecklistEntry = {
  portal: string; label: string; url: string; expiry_hint: string;
  collected: boolean; count: number;
  credentials: Array<{ id: string; name: string; portal?: string; username_masked: string; expires_at?: string; days_to_expiry?: number; expiry_status?: string }>;
};
export type ClientChecklist = {
  client_id: string; client_name: string;
  portals: ClientChecklistEntry[];
  collected_count: number; pending_count: number; total: number;
  other_credentials: Array<{ id: string; name: string; portal?: string; username_masked: string }>;
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

export type AgingDetail = { summary: Record<string, { amount: number; count: number }>; total_outstanding: number; total_invoices: number; detail: Record<string, { amount: number; count: number; invoices: Array<{ id: string; invoice_number: string; client_id: string; client_name: string; outstanding: number; due_date: string }> }> };
export type RevenueByClientRow = { client_id: string; client_name: string; billed: number; collected: number; outstanding: number; invoice_count: number };
export type RevenueByServiceRow = { service: string; sac_code: string; amount: number; gst: number; total: number; invoice_count: number };
export type GstLiability = { totals: { cgst: number; sgst: number; igst: number; total: number }; monthly: Array<{ month: string; cgst: number; sgst: number; igst: number; total: number; invoice_count: number }> };
export type MonthlyMIS = { rows: Array<{ month: string; billed: number; collected: number; outstanding: number; invoice_count: number; collection_rate: number }>; totals: { billed: number; collected: number; outstanding: number; collection_rate: number } };

export type BDLead = {
  id: string; tenant_id: string; company_name: string;
  contact_name?: string; email?: string; phone?: string; source?: string;
  status: "New" | "Contacted" | "Meeting Scheduled" | "Proposal Sent" | "Won" | "Lost";
  priority: "High" | "Medium" | "Low";
  estimated_value?: number; services?: string[]; owner: string;
  next_follow_up?: string; is_overdue?: boolean; notes?: string;
  created_at: string; updated_at?: string;
};
export type BDFollowUp = { id: string; lead_id: string; type: string; summary: string; scheduled_for?: string; done: boolean; created_by: string; created_at: string };
export type BDSummary = { by_status: Record<string, number>; total: number; won_value: number; pipeline_value: number; upcoming: Array<{ id: string; company_name: string; due_date: string; days_left: number }> };

export type AuditEntry = {
  id: string; actorId?: string | null; action?: string | null; entity?: string | null;
  entityId?: string | null; method?: string | null; path?: string | null; ip?: string | null;
  userAgent?: string | null; statusCode?: number | null; createdAt?: string | null;
};

// ── API modules ─────────────────────────────────────────────────
export const ClientsAPI = {
  list: () => apiFetch("/api/v1/clients/") as Promise<Client[]>,
  get: (id: string) => apiFetch(`/api/v1/clients/${id}`) as Promise<Client>,
  create: (data: ClientPayload) => apiFetch("/api/v1/clients/", { method: "POST", body: JSON.stringify(data) }) as Promise<Client>,
  update: (id: string, data: ClientPayload) => apiFetch(`/api/v1/clients/${id}`, { method: "PATCH", body: JSON.stringify(data) }) as Promise<Client>,
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
  portals: () => apiFetch("/api/v1/credentials/portals") as Promise<{ portals: PortalInfo[]; default_expire_days: number }>,
  checklist: (clientId: string) => apiFetch(`/api/v1/credentials/checklist?client_id=${clientId}`) as Promise<ClientChecklist>,
  create: (data: { name: string; client_id?: string; portal?: string; url?: string; username: string; password: string; notes?: string; expires_at?: string }) =>
    apiFetch("/api/v1/credentials/", { method: "POST", body: JSON.stringify(data) }) as Promise<Credential>,
  update: (id: string, data: { name?: string; portal?: string; url?: string; username?: string; password?: string; notes?: string; expires_at?: string }) =>
    apiFetch(`/api/v1/credentials/${id}`, { method: "PATCH", body: JSON.stringify(data) }) as Promise<Credential>,
  remove: (id: string) => apiFetch(`/api/v1/credentials/${id}`, { method: "DELETE" }) as Promise<{ message: string }>,
  reveal: (id: string) => apiFetch(`/api/v1/credentials/${id}/reveal`, { method: "POST" }) as Promise<CredentialReveal>,
  accessLogs: (credentialId?: string) => {
    const q = credentialId ? `?credential_id=${credentialId}` : "";
    return apiFetch(`/api/v1/credentials/access-logs${q}`) as Promise<AccessLog[]>;
  },
};

export const ReportsAPI = {
  aging: () => apiFetch("/api/v1/reports/receivables-aging") as Promise<AgingDetail>,
  revenueByClient: () => apiFetch("/api/v1/reports/revenue-by-client") as Promise<{ rows: RevenueByClientRow[]; grand_total: number }>,
  revenueByService: () => apiFetch("/api/v1/reports/revenue-by-service") as Promise<{ rows: RevenueByServiceRow[]; grand_total: number }>,
  gstLiability: () => apiFetch("/api/v1/reports/gst-liability") as Promise<GstLiability>,
  monthlyMIS: () => apiFetch("/api/v1/reports/monthly-mis") as Promise<MonthlyMIS>,
};

export const BDAPI = {
  list: (params?: { status?: string; owner?: string; priority?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.owner) q.set("owner", params.owner);
    if (params?.priority) q.set("priority", params.priority);
    const qs = q.toString();
    return apiFetch(`/api/v1/bd/leads${qs ? "?" + qs : ""}`) as Promise<BDLead[]>;
  },
  summary: () => apiFetch("/api/v1/bd/leads/summary") as Promise<BDSummary>,
  create: (data: Partial<BDLead>) => apiFetch("/api/v1/bd/leads", { method: "POST", body: JSON.stringify(data) }) as Promise<BDLead>,
  update: (id: string, data: Partial<BDLead>) => apiFetch(`/api/v1/bd/leads/${id}`, { method: "PATCH", body: JSON.stringify(data) }) as Promise<BDLead>,
  remove: (id: string) => apiFetch(`/api/v1/bd/leads/${id}`, { method: "DELETE" }) as Promise<{ message: string }>,
  followUps: (leadId: string) => apiFetch(`/api/v1/bd/leads/${leadId}/followups`) as Promise<BDFollowUp[]>,
  addFollowUp: (leadId: string, data: { type: string; summary: string; scheduled_for?: string }) =>
    apiFetch(`/api/v1/bd/leads/${leadId}/followups`, { method: "POST", body: JSON.stringify(data) }) as Promise<BDFollowUp>,
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
