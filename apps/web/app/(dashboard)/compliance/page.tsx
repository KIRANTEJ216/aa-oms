"use client";

import { useEffect, useState } from "react";
import { ComplianceAPI, ClientsAPI, type ComplianceFiling, type ComplianceHealth, type ComplianceType, type Client } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CalendarCheck, AlertTriangle, CheckCircle2, Plus, RefreshCw, ListChecks, XCircle } from "lucide-react";

const HEALTH_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  Green:  { bg: "bg-green-100",  text: "text-green-800",  label: "On Track" },
  Amber:  { bg: "bg-amber-100",  text: "text-amber-800",  label: "Due < 7 days" },
  Red:    { bg: "bg-red-100",    text: "text-red-800",    label: "Overdue" },
};

export default function CompliancePage() {
  const [filings, setFilings] = useState<ComplianceFiling[]>([]);
  const [health, setHealth] = useState<ComplianceHealth | null>(null);
  const [types, setTypes] = useState<ComplianceType[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "Green" | "Amber" | "Red">("all");
  const [showCreate, setShowCreate] = useState(false);
  const [checklistCode, setChecklistCode] = useState<string | null>(null);
  const [checklistItems, setChecklistItems] = useState<string[]>([]);
  const [filingChecklist, setFilingChecklist] = useState<{ filing: ComplianceFiling; items: string[]; progress: Record<string, boolean> } | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [f, h, t, c] = await Promise.all([
        ComplianceAPI.calendar(),
        ComplianceAPI.health(),
        ComplianceAPI.types(),
        ClientsAPI.list().catch(() => []),
      ]);
      setFilings(f);
      setHealth(h);
      setTypes(t);
      setClients(c);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function openChecklist(code: string) {
    try {
      const c = await ComplianceAPI.checklist(code);
      setChecklistCode(code);
      setChecklistItems(c.items);
    } catch (e: any) { setError(e.message); }
  }

  async function openFilingChecklist(filing: ComplianceFiling) {
    try {
      const c = await ComplianceAPI.checklist(filing.compliance_code);
      setFilingChecklist({
        filing,
        items: c.items,
        progress: filing.checklist_progress || {},
      });
    } catch (e: any) { setError(e.message); }
  }

  async function toggleStep(filingId: string, index: number, checked: boolean) {
    const fc = filingChecklist;
    if (!fc) return;
    const progress = { ...fc.progress, [String(index)]: checked };
    const allDone = fc.items.every((_, i) => progress[String(i)] === true);
    setFilingChecklist({ ...fc, progress });
    // Auto-flip status to Filed when all steps done; back to Pending if any unchecked
    if (allDone && fc.filing.status !== "Filed") await toggleFiled(filingId, true);
    else if (!allDone && fc.filing.status === "Filed") await toggleFiled(filingId, false);
    try {
      const updated = await ComplianceAPI.updateFiling(filingId, { checklist_progress: progress });
      setFilings(fl => fl.map(f => (f.id === filingId ? updated : f)));
    } catch (e: any) { setError(e.message); }
  }

  async function toggleFiled(id: string, filed: boolean) {
    try {
      await ComplianceAPI.updateFiling(id, filed ? { status: "Filed", filed_at: new Date().toISOString().slice(0,10) } : { status: "Pending", filed_at: null as any });
    } catch (e: any) { setError(e.message); }
  }

  async function markFiled(id: string) {
    try {
      await ComplianceAPI.updateFiling(id, { status: "Filed", filed_at: new Date().toISOString().slice(0,10) });
      await refresh();
    } catch (e: any) { setError(e.message); }
  }

  const filtered = filter === "all" ? filings : filings.filter(f => f.health === filter);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Compliance</h1>
          <p className="text-sm text-slate-500">GST · ITR · TDS · ROC · Advance Tax</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={filter} onChange={e => setFilter(e.target.value as any)} className="h-9 rounded-md border px-2 text-sm">
            <option value="all">All filings</option>
            <option value="Green">Green (on track)</option>
            <option value="Amber">Amber (≤7 days)</option>
            <option value="Red">Red (overdue)</option>
          </select>
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
          <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4 mr-1" /> New Filing</Button>
        </div>
      </div>

      {/* Health dashboard */}
      {health && (
        <div className="grid gap-3 md:grid-cols-4">
          <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Total filings</p><p className="text-2xl font-bold">{health.total}</p></CardContent></Card>
          <Card className="border-green-300 bg-green-50"><CardContent className="pt-6 flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-green-600" /><div><p className="text-xs text-green-700">On track</p><p className="text-2xl font-bold text-green-800">{health.by_health.Green}</p></div></CardContent></Card>
          <Card className="border-amber-300 bg-amber-50"><CardContent className="pt-6 flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-amber-600" /><div><p className="text-xs text-amber-700">Due within 7 days</p><p className="text-2xl font-bold text-amber-800">{health.by_health.Amber}</p></div></CardContent></Card>
          <Card className="border-red-300 bg-red-50"><CardContent className="pt-6 flex items-center gap-2"><XCircle className="h-5 w-5 text-red-600" /><div><p className="text-xs text-red-700">Overdue</p><p className="text-2xl font-bold text-red-800">{health.by_health.Red}</p></div></CardContent></Card>
        </div>
      )}

      {/* Upcoming deadlines */}
      {health && health.upcoming.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2"><CalendarCheck className="h-4 w-4" /> Upcoming Deadlines</CardTitle>
            <CardDescription>Next filings requiring attention (Amber + Red)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {health.upcoming.slice(0, 8).map(u => {
              const days = u.days_until_due;
              const label = days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? "Due today" : `in ${days}d`;
              const style = HEALTH_STYLES[u.health];
              return (
                <div key={u.id} className="flex items-center justify-between text-sm border-b pb-2 last:border-0">
                  <div>
                    <p className="font-medium">{u.compliance_code} · {u.period}</p>
                    <p className="text-xs text-slate-500">Client: {clients.find(c => c.id === u.client_id)?.name || u.client_id}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${style.bg} ${style.text}`}>{label}</span>
                    <Button variant="outline" size="sm" onClick={() => markFiled(u.id)}>Mark filed</Button>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}
      {loading && <p className="text-sm text-slate-500">Loading compliance…</p>}

      {/* Filings table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filings ({filtered.length})</CardTitle>
          <CardDescription>Click “Checklist” to see filing steps for any compliance type</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[820px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">Compliance</th>
                <th className="text-left p-3">Client</th>
                <th className="text-left p-3">Period</th>
                <th className="text-left p-3">Due</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Health</th>
                <th className="text-left p-3">Step progress</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(f => {
                const style = HEALTH_STYLES[f.health];
                return (
                  <tr key={f.id} className="border-b hover:bg-slate-50">
                    <td className="p-3">
                      <p className="font-medium">{f.compliance_code}</p>
                      <p className="text-xs text-slate-500">{f.compliance_name}</p>
                    </td>
                    <td className="p-3 text-slate-600">{f.client_name}</td>
                    <td className="p-3 text-slate-600">{f.period}</td>
                    <td className="p-3 text-slate-600">{f.actual_due_date}</td>
                    <td className="p-3">
                      {f.status === "Filed" ?
                        <span className="rounded bg-green-100 text-green-700 text-xs px-2 py-0.5">✓ Filed {f.filed_at}</span> :
                        <span className="rounded bg-slate-100 text-slate-700 text-xs px-2 py-0.5">Pending</span>
                      }
                    </td>
                    <td className="p-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${style.bg} ${style.text}`}>{f.health}</span>
                    </td>
                    <td className="p-3">
                      {f.checklist_total ? (
                        <div className="flex items-center gap-1.5">
                          <div className="w-14 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div className="h-full bg-blue-600" style={{ width: `${Math.round(((f.checklist_done || 0) / f.checklist_total) * 100)}%` }} />
                          </div>
                          <span className="text-xs text-slate-500 whitespace-nowrap">{f.checklist_done}/{f.checklist_total} steps</span>
                        </div>
                      ) : <span className="text-slate-300 text-xs">—</span>}
                    </td>
                    <td className="p-3 text-right">
                      <Button variant="outline" size="sm" onClick={() => openFilingChecklist(f)}>
                        <ListChecks className="h-3 w-3 mr-1" /> Checklist
                      </Button>
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && !loading && (
                <tr><td colSpan={8} className="p-6 text-center text-slate-400 italic">No filings — create one to get started.</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </CardContent>
      </Card>

      {/* Compliance types reference */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Compliance Types</CardTitle>
          <CardDescription>Standard due dates per Indian regulations (PDF p.12-14)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 md:grid-cols-3">
            {types.map(t => (
              <div key={t.code} className="border rounded p-2 text-sm">
                <p className="font-medium">{t.code}</p>
                <p className="text-xs text-slate-500">{t.name}</p>
                <p className="text-xs text-slate-400 mt-1">{t.frequency} · due {t.standardDueDate}</p>
                <button onClick={() => openChecklist(t.code)} className="text-xs text-blue-600 mt-1 hover:underline">View checklist →</button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Read-only reference checklist modal (compliance types) */}
      {checklistCode && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setChecklistCode(null)}>
          <Card className="w-full max-w-md" onClick={e => e.stopPropagation()}>
            <CardHeader>
              <CardTitle>{checklistCode} — Filing Checklist</CardTitle>
              <CardDescription>Step-by-step guide for compliance filing</CardDescription>
            </CardHeader>
            <CardContent>
              <ol className="space-y-2 list-decimal list-inside text-sm">
                {checklistItems.map((item, i) => (
                  <li key={i} className="leading-relaxed">{item}</li>
                ))}
              </ol>
              <div className="flex justify-end mt-4">
                <Button variant="outline" onClick={() => setChecklistCode(null)}>Close</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filing checklist modal with step checkboxes */}
      {filingChecklist && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setFilingChecklist(null)}>
          <Card className="w-full max-w-lg" onClick={e => e.stopPropagation()}>
            <CardHeader>
              <CardTitle>{filingChecklist.filing.compliance_code} — Filing Checklist</CardTitle>
              <CardDescription>
                {filingChecklist.filing.client_name || filingChecklist.filing.client_id} · {filingChecklist.filing.period} · due {filingChecklist.filing.actual_due_date}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 text-sm">
                {filingChecklist.items.map((item, i) => {
                  const checked = filingChecklist.progress[String(i)] === true;
                  return (
                    <label key={i} className={`flex items-start gap-2 rounded-md border p-2 cursor-pointer transition ${checked ? "bg-green-50 border-green-200" : "hover:bg-slate-50"}`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={e => toggleStep(filingChecklist.filing.id, i, e.target.checked)}
                        className="mt-0.5 h-4 w-4 accent-green-600"
                      />
                      <span className={checked ? "line-through text-slate-500" : ""}>{i + 1}. {item}</span>
                    </label>
                  );
                })}
                <p className="text-xs text-slate-500">
                  {filingChecklist.items.filter((_, i) => filingChecklist.progress[String(i)] === true).length}/{filingChecklist.items.length} steps done
                  {filingChecklist.items.every((_, i) => filingChecklist.progress[String(i)] === true) && <span className="text-green-700 font-medium"> — all steps complete, filing marked as Filed ✓</span>}
                </p>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setFilingChecklist(null)}>Close</Button>
                  <Button variant="outline" onClick={() => markFiled(filingChecklist.filing.id)}>Mark filed</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {showCreate && <CreateFilingDialog clients={clients} types={types} onClose={() => setShowCreate(false)} onCreated={refresh} />}
    </div>
  );
}

function CreateFilingDialog({ clients, types, onClose, onCreated }: { clients: Client[]; types: ComplianceType[]; onClose: () => void; onCreated: () => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    client_id: clients[0]?.id || "",
    compliance_code: types[0]?.code || "GSTR1",
    period: new Date().getFullYear() + "-" + (new Date().getFullYear() + 1).toString().slice(-2),
    actual_due_date: today,
    notes: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setSaving(true);
    try {
      await ComplianceAPI.createFiling(form);
      onCreated();
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-lg">
        <CardHeader><CardTitle>New Compliance Filing</CardTitle><CardDescription>Track a new filing for a client</CardDescription></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <div><Label>Client</Label>
              <select value={form.client_id} onChange={e => setForm({...form, client_id: e.target.value})} required className="w-full h-10 rounded-md border px-2 text-sm">
                <option value="">— Select —</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name} ({c.pan})</option>)}
              </select>
            </div>
            <div><Label>Compliance type</Label>
              <select value={form.compliance_code} onChange={e => setForm({...form, compliance_code: e.target.value})} className="w-full h-10 rounded-md border px-2 text-sm">
                {types.map(t => <option key={t.code} value={t.code}>{t.code} — {t.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Period</Label><Input value={form.period} onChange={e => setForm({...form, period: e.target.value})} placeholder="2024-25 or Q1 FY24-25" required /></div>
              <div><Label>Due date</Label><Input type="date" value={form.actual_due_date} onChange={e => setForm({...form, actual_due_date: e.target.value})} required /></div>
            </div>
            <div><Label>Notes (optional)</Label><Input value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} /></div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Creating…" : "Create Filing"}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
