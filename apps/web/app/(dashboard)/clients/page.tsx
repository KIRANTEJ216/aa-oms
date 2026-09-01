"use client";

import { useEffect, useState } from "react";
import { ClientsAPI, type Client } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Users, Plus, Search, RefreshCw, Pencil, Trash2, Building2, User } from "lucide-react";

const CLIENT_TYPES = ["Individual", "HUF", "Company", "LLP", "Trust", "Partnership Firm"];
const SERVICES = ["GST", "ITR", "TDS", "Roc", "Accounting", "Payroll"];

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  async function refresh() {
    setLoading(true); setError(null);
    try {
      setClients(await ClientsAPI.list());
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, []);

  async function remove(id: string) {
    if (!confirm("Delete this client? This cannot be undone.")) return;
    try { await ClientsAPI.remove(id); await refresh(); }
    catch (e: any) { setError(e.message); }
  }

  const q = query.trim().toLowerCase();
  const filtered = q ? clients.filter(c =>
    c.name.toLowerCase().includes(q) ||
    (c.pan || "").toLowerCase().includes(q) ||
    (c.gstin || "").toLowerCase().includes(q) ||
    (c.email || "").toLowerCase().includes(q)
  ) : clients;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2"><Users className="h-6 w-6" /> Clients</h1>
          <p className="text-sm text-slate-500">Individual · HUF · Company · LLP · Trust · Partnership</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
          <Button onClick={() => { setEditingId(null); setShowForm(true); }}><Plus className="h-4 w-4 mr-1" /> New Client</Button>
        </div>
      </div>

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}

      {/* Stat cards */}
      <div className="grid gap-3 md:grid-cols-4">
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Total clients</p><p className="text-2xl font-bold">{clients.length}</p></CardContent></Card>
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Companies</p><p className="text-2xl font-bold">{clients.filter(c => c.type === "Company").length}</p></CardContent></Card>
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Individuals</p><p className="text-2xl font-bold">{clients.filter(c => c.type === "Individual").length}</p></CardContent></Card>
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Firms / LLP / HUF</p><p className="text-2xl font-bold">{clients.filter(c => !["Company", "Individual"].includes(c.type)).length}</p></CardContent></Card>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by name, PAN, GSTIN, or email…" className="pl-9" />
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">All Clients ({filtered.length})</CardTitle>
          <CardDescription>Duplicate PAN detection + search by PAN/GSTIN</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="text-left p-3">Client</th>
                  <th className="text-left p-3">Type</th>
                  <th className="text-left p-3">PAN</th>
                  <th className="text-left p-3">Aadhaar</th>
                  <th className="text-left p-3">GSTIN</th>
                  <th className="text-left p-3">Contact</th>
                  <th className="text-left p-3">Services</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(c => (
                  <tr key={c.id} className="border-b hover:bg-slate-50">
                    <td className="p-3">
                      <p className="font-medium">{c.type === "Company" || c.type === "LLP" || c.type === "Trust" || c.type === "Partnership Firm" ? <Building2 className="h-3 w-3 inline mr-1" /> : <User className="h-3 w-3 inline mr-1" />}{c.name}</p>
                      <p className="text-xs text-slate-500">{c.email}</p>
                    </td>
                    <td className="p-3"><span className="rounded bg-slate-100 text-slate-700 text-xs px-2 py-0.5">{c.type}</span></td>
                    <td className="p-3 font-mono text-xs">{c.pan}</td>
                    <td className="p-3 font-mono text-xs">
                      {c.aadhaar_masked ? <span title="Aadhaar stored encrypted, shown masked">{c.aadhaar_masked}</span> : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="p-3 font-mono text-xs">{c.gstin || "—"}</td>
                    <td className="p-3 text-xs text-slate-600">{c.mobile}</td>
                    <td className="p-3 text-xs">{c.services.map(s => <span key={s} className="rounded bg-blue-50 text-blue-700 px-1.5 py-0.5 mr-1">{s}</span>)}</td>
                    <td className="p-3 text-right space-x-1 whitespace-nowrap">
                      <Button variant="outline" size="sm" onClick={() => { setEditingId(c.id); setShowForm(true); }}><Pencil className="h-3 w-3" /></Button>
                      <Button variant="outline" size="sm" onClick={() => remove(c.id)}><Trash2 className="h-3 w-3" /></Button>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && !loading && (
                  <tr><td colSpan={8} className="p-6 text-center text-slate-400 italic">{query ? "No clients match your search." : "No clients yet — click \"New Client\" to add one."}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-slate-500">Loading clients…</p>}

      {showForm && (
        <ClientDialog
          editId={editingId}
          existing={editingId ? clients.find(c => c.id === editingId) : undefined}
          onClose={() => setShowForm(false)}
          onSaved={refresh}
        />
      )}
    </div>
  );
}

function ClientDialog({ editId, existing, onClose, onSaved }: { editId: string | null; existing?: Client; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    type: existing?.type || "Individual",
    name: existing?.name || "",
    pan: existing?.pan || "",
    gstin: existing?.gstin || "",
    tan: existing?.tan || "",
    cin: existing?.cin || "",
    llpin: existing?.llpin || "",
    email: existing?.email || "",
    mobile: existing?.mobile || "",
    address: existing?.address || "",
    engagement_manager: existing?.engagement_manager || "",
    dob_or_incorporation: existing?.dob_or_incorporation || "",
    services: existing?.services || [],
    aadhaar: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function toggleService(s: string) {
    setForm(f => ({ ...f, services: f.services.includes(s) ? f.services.filter(x => x !== s) : [...f.services, s] }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const missing: string[] = [];
    if (form.name.trim().length < 2) missing.push("Name");
    if (form.pan.trim().length < 10) missing.push("PAN");
    if (!form.email.trim()) missing.push("Email");
    if (form.mobile.replace(/\s+/g, "").length < 10) missing.push("Mobile");
    if (form.address.trim().length < 5) missing.push("Address");
    if (!form.dob_or_incorporation) missing.push("DOB / Incorporation");
    if (!form.engagement_manager.trim()) missing.push("Engagement Manager");
    if (missing.length) {
      setError(`Missing required fields: ${missing.join(", ")}`);
      return;
    }
    const aadhaarDigits = form.aadhaar.replace(/\s+/g, "");
    if (form.aadhaar && !/^\d{12}$/.test(aadhaarDigits)) {
      setError("Aadhaar must be 12 digits (e.g. 1234 5678 9012)");
      return;
    }
    setSaving(true);
    try {
      if (editId && existing) {
        const data: any = {};
        (["type","name","pan","gstin","tan","cin","llpin","email","mobile","address","engagement_manager","dob_or_incorporation"] as const).forEach(k => {
          if (form[k] !== existing[k]) data[k] = form[k];
        });
        if (JSON.stringify(form.services) !== JSON.stringify(existing.services)) data.services = form.services;
        if (form.aadhaar.trim()) data.aadhaar = aadhaarDigits;
        await ClientsAPI.update(editId, data);
      } else {
        await ClientsAPI.create({ ...form, aadhaar: aadhaarDigits || undefined });
      }
      onSaved();
      onClose();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader><CardTitle>{editId ? "Edit Client" : "New Client"}</CardTitle><CardDescription>Duplicate PAN detection is automatic (409 on conflict)</CardDescription></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Type</Label>
                <select value={form.type} onChange={e => setForm({...form, type: e.target.value})} className="w-full h-10 rounded-md border px-2 text-sm">
                  {CLIENT_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div><Label>Name *</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} required /></div>
              <div><Label>PAN *</Label><Input value={form.pan} onChange={e => setForm({...form, pan: e.target.value.toUpperCase()})} placeholder="ABCDE1234F" required /></div>
              <div><Label>Aadhaar {editId && existing?.has_aadhaar && <span className="text-xs text-slate-400 font-normal">(stored masked: {existing.aadhaar_masked})</span>} {editId && "(blank to keep)"}</Label><Input value={form.aadhaar} onChange={e => setForm({...form, aadhaar: e.target.value})} placeholder="1234 5678 9012 (encrypted at rest)" inputMode="numeric" /></div>
              <div><Label>GSTIN</Label><Input value={form.gstin} onChange={e => setForm({...form, gstin: e.target.value.toUpperCase()})} placeholder="22AAAAA0000A1Z5" /></div>
              <div><Label>TAN</Label><Input value={form.tan} onChange={e => setForm({...form, tan: e.target.value.toUpperCase()})} placeholder="AAAA12345A" /></div>
              <div><Label>CIN / LLPIN</Label><Input value={form.cin} onChange={e => setForm({...form, cin: e.target.value.toUpperCase()})} /></div>
              <div><Label>Email *</Label><Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} /></div>
              <div><Label>Mobile *</Label><Input value={form.mobile} onChange={e => setForm({...form, mobile: e.target.value})} placeholder="+91 98765 43210" /></div>
              <div><Label>DOB / Incorporation *</Label><Input type="date" value={form.dob_or_incorporation} onChange={e => setForm({...form, dob_or_incorporation: e.target.value})} /></div>
              <div><Label>Engagement Manager *</Label><Input value={form.engagement_manager} onChange={e => setForm({...form, engagement_manager: e.target.value})} /></div>
            </div>
            <div><Label>Address *</Label><Input value={form.address} onChange={e => setForm({...form, address: e.target.value})} /></div>
            <div>
              <Label>Engaged Services</Label>
              <div className="flex flex-wrap gap-2 mt-1">
                {SERVICES.map(s => (
                  <button key={s} type="button" onClick={() => toggleService(s)}
                    className={`rounded-full border px-3 py-1 text-xs transition ${form.services.includes(s) ? "bg-slate-900 text-white border-slate-900" : "bg-white hover:bg-slate-50"}`}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving…" : editId ? "Update" : "Create Client"}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
