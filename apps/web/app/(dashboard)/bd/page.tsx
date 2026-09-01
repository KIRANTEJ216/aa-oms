"use client";

import { useEffect, useState } from "react";
import { BDAPI, type BDLead, type BDFollowUp, type BDSummary } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Briefcase, Plus, RefreshCw, TrendingUp, Mail, Phone, CalendarClock, MessageSquare, Trash2, ChevronRight } from "lucide-react";

const STATUSES = ["New", "Contacted", "Meeting Scheduled", "Proposal Sent", "Won", "Lost"];
const SOURCES = ["Referral", "Walk-in", "LinkedIn", "Website", "Cold Call", "Existing Client", "Other"];
const PRIORITIES = ["High", "Medium", "Low"];
const FOLLOWUP_TYPES = ["Call", "Email", "Meeting", "Proposal", "Note"];

const STATUS_STYLE: Record<string, string> = {
  "New": "bg-slate-100 text-slate-700",
  "Contacted": "bg-blue-50 text-blue-700",
  "Meeting Scheduled": "bg-violet-50 text-violet-700",
  "Proposal Sent": "bg-amber-50 text-amber-800",
  "Won": "bg-green-100 text-green-700",
  "Lost": "bg-red-50 text-red-600",
};

const fmt = (n: number) => "₹" + (n || 0).toLocaleString("en-IN");

export default function BDLeadPage() {
  const [leads, setLeads] = useState<BDLead[]>([]);
  const [summary, setSummary] = useState<BDSummary | null>(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [active, setActive] = useState<{ lead: BDLead; followUps: BDFollowUp[] } | null>(null);

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const [l, s] = await Promise.all([BDAPI.list(), BDAPI.summary()]);
      setLeads(l); setSummary(s);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, []);

  async function openDetail(lead: BDLead) {
    try {
      const followUps = await BDAPI.followUps(lead.id);
      setActive({ lead, followUps });
    } catch (e: any) { setError(e.message); }
  }

  async function deleteLead(id: string) {
    if (!confirm("Delete this lead? This cannot be undone.")) return;
    try { await BDAPI.remove(id); setActive(null); await refresh(); }
    catch (e: any) { setError(e.message); }
  }

  const filtered = filter === "all" ? leads : leads.filter(l => l.status === filter);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2"><Briefcase className="h-6 w-6" /> Business Development</h1>
          <p className="text-sm text-slate-500">Pipeline · follow-ups · pitching new clients · sending mails</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
          <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4 mr-1" /> New Lead</Button>
        </div>
      </div>

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}

      {/* Pipeline summary */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {STATUSES.map(s => (
            <Card key={s} className={s === "Won" ? "border-green-200 bg-green-50" : ""}>
              <CardContent className="pt-6">
                <p className="text-xs text-slate-500">{s}</p>
                <p className="text-2xl font-bold">{summary.by_status[s] || 0}</p>
              </CardContent>
            </Card>
          ))}
          <Card className="col-span-2 md:col-span-3 bg-blue-50"><CardContent className="pt-6"><p className="text-xs text-blue-700">Pipeline value (open leads)</p><p className="text-2xl font-bold">{fmt(summary.pipeline_value)}</p></CardContent></Card>
          <Card className="col-span-2 md:col-span-3 bg-green-50"><CardContent className="pt-6"><p className="text-xs text-green-700">Won value (closed)</p><p className="text-2xl font-bold">{fmt(summary.won_value)}</p></CardContent></Card>
        </div>
      )}

      {/* Upcoming follow-ups */}
      {summary && summary.upcoming.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2"><CalendarClock className="h-4 w-4" /> Follow-ups due within 7 days</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {summary.upcoming.map(u => (
              <div key={u.id} className="flex items-center justify-between text-sm border-b pb-2 last:border-0">
                <div>
                  <p className="font-medium">{u.company_name}</p>
                  <p className="text-xs text-slate-500">Follow-up due {u.due_date}</p>
                </div>
                <button className="text-xs text-blue-600 hover:underline" onClick={() => { const l = leads.find(x => x.id === u.id); if (l) openDetail(l); }}>Open →</button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Filter + leads table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-base">Leads ({filtered.length})</CardTitle>
            <select value={filter} onChange={e => setFilter(e.target.value)} className="h-9 rounded-md border px-2 text-sm">
              <option value="all">All statuses</option>
              {STATUSES.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <CardDescription>Click a row to manage follow-ups, change status and send an email</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm min-w-[820px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">Company</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Priority</th>
                <th className="text-left p-3">Owner</th>
                <th className="text-left p-3">Next follow-up</th>
                <th className="text-right p-3">Est. value</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(l => (
                <tr key={l.id} className="border-b hover:bg-slate-50 cursor-pointer" onClick={() => openDetail(l)}>
                  <td className="p-3">
                    <p className="font-medium">{l.company_name}</p>
                    <p className="text-xs text-slate-500">{l.source} · {l.contact_name || "—"}</p>
                  </td>
                  <td className="p-3"><span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE[l.status] || "bg-slate-100 text-slate-700"}`}>{l.status}</span></td>
                  <td className="p-3">
                    <span className={`rounded px-2 py-0.5 text-xs ${l.priority === "High" ? "bg-red-50 text-red-700" : l.priority === "Medium" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-600"}`}>{l.priority}</span>
                  </td>
                  <td className="p-3 text-slate-600">{l.owner}</td>
                  <td className="p-3">
                    {l.next_follow_up ? (
                      <span className={`text-xs ${l.is_overdue ? "text-red-600 font-medium" : "text-slate-500"}`}>
                        {l.next_follow_up.slice(0, 10)}{l.is_overdue && " · overdue"}
                      </span>
                    ) : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="p-3 text-right font-medium">{l.estimated_value ? fmt(l.estimated_value) : "—"}</td>
                  <td className="p-3 text-right text-slate-300"><ChevronRight className="h-4 w-4 inline" /></td>
                </tr>
              ))}
              {filtered.length === 0 && !loading && (
                <tr><td colSpan={7} className="p-6 text-center text-slate-400 italic">No leads yet — add your first prospect.</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-slate-500">Loading leads…</p>}

      {showCreate && <LeadDialog onClose={() => setShowCreate(false)} onSaved={refresh} />}
      {active && <LeadDetail lead={active.lead} followUps={active.followUps} onClose={() => setActive(null)} onUpdated={async () => { await refresh(); await openDetail(active.lead); }} onDelete={deleteLead} />}
    </div>
  );
}

function LeadDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    company_name: "",
    contact_name: "",
    email: "",
    phone: "",
    source: "Referral",
    status: "New",
    priority: "Medium",
    estimated_value: "",
    owner: "",
    next_follow_up: "",
    notes: "",
    services: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (form.company_name.trim().length < 2) { setError("Company name is required"); return; }
    if (!form.owner.trim()) { setError("Owner (responsible staff) is required"); return; }
    setSaving(true);
    try {
      await BDAPI.create({
        company_name: form.company_name.trim(),
        contact_name: form.contact_name.trim() || undefined,
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        source: form.source,
        status: form.status as BDLead["status"],
        priority: form.priority as BDLead["priority"],
        estimated_value: form.estimated_value ? parseFloat(form.estimated_value) : undefined,
        owner: form.owner.trim(),
        next_follow_up: form.next_follow_up || undefined,
        notes: form.notes.trim() || undefined,
        services: form.services.split(",").map(s => s.trim()).filter(Boolean),
      });
      onSaved(); onClose();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <CardHeader><CardTitle>New Lead</CardTitle><CardDescription>Track a new prospect · pitch, follow-up and conversion</CardDescription></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Company name *</Label><Input value={form.company_name} onChange={e => setForm({...form, company_name: e.target.value})} required /></div>
              <div><Label>Contact person</Label><Input value={form.contact_name} onChange={e => setForm({...form, contact_name: e.target.value})} /></div>
              <div><Label>Email</Label><Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} /></div>
              <div><Label>Phone</Label><Input value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} /></div>
              <div><Label>Source</Label>
                <select value={form.source} onChange={e => setForm({...form, source: e.target.value})} className="w-full h-10 rounded-md border px-2 text-sm">
                  {SOURCES.map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div><Label>Status</Label>
                <select value={form.status} onChange={e => setForm({...form, status: e.target.value})} className="w-full h-10 rounded-md border px-2 text-sm">
                  {STATUSES.map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div><Label>Priority</Label>
                <select value={form.priority} onChange={e => setForm({...form, priority: e.target.value})} className="w-full h-10 rounded-md border px-2 text-sm">
                  {PRIORITIES.map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div><Label>Est. annual fees (INR)</Label><Input type="number" min="0" value={form.estimated_value} onChange={e => setForm({...form, estimated_value: e.target.value})} placeholder="50000" /></div>
              <div><Label>Owner (responsible) *</Label><Input value={form.owner} onChange={e => setForm({...form, owner: e.target.value})} required /></div>
              <div><Label>Next follow-up date</Label><Input type="date" value={form.next_follow_up} onChange={e => setForm({...form, next_follow_up: e.target.value})} /></div>
            </div>
            <div><Label>Services likely (comma separated)</Label><Input value={form.services} onChange={e => setForm({...form, services: e.target.value})} placeholder="GST, ITR, Accounting" /></div>
            <div><Label>Notes</Label><Input value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} /></div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Create Lead"}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function LeadDetail({ lead, followUps, onClose, onUpdated, onDelete }: { lead: BDLead; followUps: BDFollowUp[]; onClose: () => void; onUpdated: () => void; onDelete: (id: string) => void }) {
  const [status, setStatus] = useState(lead.status);
  const [followUp, setFollowUp] = useState({ type: "Call", summary: "", scheduled_for: "" });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function changeStatus(s: BDLead["status"]) {
    setError(null);
    try {
      await BDAPI.update(lead.id, { status: s });
      setStatus(s);
      onUpdated();
    } catch (e: any) { setError(e.message); }
  }

  async function addFollowUp(e: React.FormEvent) {
    e.preventDefault();
    if (!followUp.summary.trim()) return;
    setError(null); setSaving(true);
    try {
      await BDAPI.addFollowUp(lead.id, { type: followUp.type, summary: followUp.summary.trim(), scheduled_for: followUp.scheduled_for || undefined });
      setFollowUp({ type: "Call", summary: "", scheduled_for: "" });
      onUpdated();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  const mailto = lead.email
    ? `mailto:${lead.email}?subject=${encodeURIComponent(`Aarav Advisors — ${lead.company_name}`)}&body=${encodeURIComponent(`Dear ${lead.contact_name || "Sir/Madam"},\n\nFollowing up on our discussion about how Aarav Advisors can help with ${(lead.services || []).join(", ") || "your compliance needs"}.\n\nRegards,\nAarav Advisors`)}`
    : null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-2"><Briefcase className="h-4 w-4" /> {lead.company_name}</CardTitle>
              <CardDescription className="mt-1">
                {lead.source} · Owner: {lead.owner} · Est. value {lead.estimated_value ? fmt(lead.estimated_value) : "—"}
                <br />{lead.contact_name && `${lead.contact_name} · `}{lead.email} · {lead.phone || ""}
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => onDelete(lead.id)} title="Delete"><Trash2 className="h-3 w-3" /></Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Status quick actions */}
          <div>
            <Label>Status</Label>
            <div className="flex gap-1 flex-wrap mt-1">
              {STATUSES.map(s => (
                <button key={s} onClick={() => changeStatus(s as BDLead["status"])}
                  className={`rounded-md border px-2 py-1 text-xs transition ${status === s ? "bg-slate-900 text-white border-slate-900" : "bg-white hover:bg-slate-50"}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Email + phone actions */}
          <div className="flex gap-2 flex-wrap">
            {mailto && <a href={mailto} className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 text-white px-3 py-2 text-sm hover:bg-blue-700"><Mail className="h-4 w-4" /> Send email</a>}
            {lead.phone && <a href={`tel:${lead.phone}`} className="inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm hover:bg-slate-50"><Phone className="h-4 w-4" /> Call</a>}
            <Button variant="outline" size="sm" onClick={onUpdated}><RefreshCw className="h-3 w-3 mr-1" /> Refresh</Button>
          </div>

          {/* Notes */}
          {lead.notes && <p className="text-sm text-slate-600 rounded-md bg-slate-50 p-2">{lead.notes}</p>}

          {/* Add follow-up */}
          <div>
            <Label>Log a follow-up</Label>
            <form onSubmit={addFollowUp} className="flex gap-2 mt-1 items-end">
              <select value={followUp.type} onChange={e => setFollowUp({...followUp, type: e.target.value})} className="h-10 rounded-md border px-2 text-sm">
                {FOLLOWUP_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
              <Input value={followUp.summary} onChange={e => setFollowUp({...followUp, summary: e.target.value})} placeholder="What happened in this interaction?" className="flex-1" required />
              <Input type="date" value={followUp.scheduled_for} onChange={e => setFollowUp({...followUp, scheduled_for: e.target.value})} className="w-40" />
              <Button type="submit" disabled={saving}><MessageSquare className="h-4 w-4" /></Button>
            </form>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          {/* Follow-up timeline */}
          <div>
            <Label>Follow-up history</Label>
            <div className="space-y-2 mt-1">
              {followUps.length === 0 && <p className="text-sm text-slate-400 italic">No follow-ups logged yet.</p>}
              {followUps.map(f => (
                <div key={f.id} className="rounded-md border p-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="rounded bg-slate-100 text-slate-700 text-xs px-2 py-0.5">{f.type}</span>
                    <span className="text-xs text-slate-400 font-mono">{f.created_at.slice(0, 16).replace("T", " ")}</span>
                  </div>
                  <p className="mt-1">{f.summary}</p>
                  {f.scheduled_for && <p className="text-xs text-slate-500 mt-0.5">Scheduled: {f.scheduled_for.slice(0, 10)}</p>}
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <Button variant="outline" onClick={onClose}>Close</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}