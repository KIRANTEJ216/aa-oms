"use client";

export type SessionUser = {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
};

export function getSessionUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem("caoms_access_token");
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return {
      id: payload.sub || "",
      email: payload.email || "",
      role: payload.role || "Client",
      tenant_id: payload.tenant_id || "aarav-advisors",
    };
  } catch {
    return null;
  }
}

export function signOut() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("caoms_access_token");
  localStorage.removeItem("caoms_temp_token");
  window.location.href = "/login";
}
