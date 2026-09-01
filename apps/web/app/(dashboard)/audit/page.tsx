"use client";

import { useEffect, useState } from "react";
import { AuditAPI, type AuditEntry } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ShieldCheck, RefreshCw } from "lucide-react";

const ACTION_STYLES: Record<string, string> = {
  LOGIN: "bg-blue-100 text-blue-700",
  AUTH: "bg-blue-100 text-blue-700",
  CREATE: "bg-green-100 text-green-700",
  UPDATE: "bg-amber-100 text-amber-700",
  DELETE: "bg-red-100 text-red-700",
  PAYMENT: "bg-purple-100 text-purple-700",
  VIEW_CREDENTIAL: "bg-red-100 text-red-700",
  EXPORT: "bg-slate-100 text-slate-700",
};

function fmtDate(s?: string | null) {
  if (!s) return "—";
  return s.slice(0, 19).replace("T", " ");
}

export default function AuditPage() {
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entityFilter, setEntityFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");

  const entityOptions = ["all", "auth", "users", "clients", "tasks", "compliance", "documents", "credentials", "invoices"];
  const actionOptions = ["all", "LOGIN", "AUTH", "CREATE", "UPDATE", "DELETE", "PAYMENT", "VIEW_CREDENTIAL", "EXPORT"];

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const params: any = { limit: 200 };
      if (entityFilter !== "all") params.entity = entityFilter;
      if (actionFilter !== "all") params.action = actionFilter;
      const res = await AuditAPI.list(params);
      setItems(res.items);
      setTotal(res.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, [entityFilter, actionFilter]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2"><ShieldCheck className="h-6 w-6" /> Audit Trail</h1>
          <p className="text-sm text-slate-500">Immutable logs · login, create, update, delete, payments, vault reveals</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
        </div>
      </div>

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select value={entityFilter} onChange={e => setEntityFilter(e.target.value)} className="h-9 rounded-md border px-2 text-sm">
          {entityOptions.map(o => <option key={o} value={o}>{o === "all" ? "All entities" : o}</option>)}
        </select>
        <select value={actionFilter} onChange={e => setActionFilter(e.target.value)} className="h-9 rounded-md border px-2 text-sm">
          {actionOptions.map(o => <option key={o} value={o}>{o === "all" ? "All actions" : o}</option>)}
        </select>
        <span className="text-sm text-slate-500 self-center">Showing {items.length} of {total} entries</span>
      </div>

      {/* Log table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Audit Log</CardTitle>
          <CardDescription>Every action is immutable and tenant-scoped</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[820px]">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="text-left p-3">When</th>
                  <th className="text-left p-3">Action</th>
                  <th className="text-left p-3">Entity</th>
                  <th className="text-left p-3">Actor</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-left p-3">IP</th>
                  <th className="text-left p-3">Path</th>
                </tr>
              </thead>
              <tbody>
                {items.map(e => (
                  <tr key={e.id} className="border-b hover:bg-slate-50">
                    <td className="p-3 text-slate-500 text-xs font-mono whitespace-nowrap">{fmtDate(e.createdAt)}</td>
                    <td className="p-3">
                      <span className={`rounded px-2 py-0.5 text-xs ${ACTION_STYLES[e.action || ""] || "bg-slate-100 text-slate-700"}`}>{e.action || "—"}</span>
                    </td>
                    <td className="p-3">
                      <p className="font-medium">{e.entity || "—"}</p>
                      {e.entityId && <p className="text-xs text-slate-400 font-mono">{e.entityId.slice(0, 12)}…</p>}
                    </td>
                    <td className="p-3 text-xs text-slate-500">{e.actorId ? e.actorId.slice(0, 8) : "system"}</td>
                    <td className="p-3 text-xs">{e.statusCode ? <span className="rounded bg-slate-100 px-1.5 py-0.5">{e.statusCode}</span> : "—"}</td>
                    <td className="p-3 text-xs text-slate-500">{e.ip || "—"}</td>
                    <td className="p-3 text-xs text-slate-400 font-mono">{e.path || "—"}</td>
                  </tr>
                ))}
                {items.length === 0 && !loading && (
                  <tr><td colSpan={7} className="p-6 text-center text-slate-400 italic">No audit entries match your filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-slate-500">Loading audit trail…</p>}
    </div>
  );
}
