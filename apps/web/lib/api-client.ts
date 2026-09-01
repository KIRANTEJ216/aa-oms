const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type FetchOpts = RequestInit & { tenantId?: string };

export async function apiFetch(path: string, opts: FetchOpts = {}) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((opts.headers as Record<string, string>) || {}),
  };
  // TENANT_MODE=single: header ignored server-side but sent for future multi-tenant
  const tenant = opts.tenantId || process.env.NEXT_PUBLIC_TENANT_MODE === "single" ? "aarav-advisors" : undefined;
  if (tenant) headers["X-Tenant-ID"] = tenant;
  const token = typeof window !== "undefined" ? localStorage.getItem("caoms_access_token") : null;
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...opts, headers, credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `API ${res.status} at ${path}`);
  }
  return res.json();
}
