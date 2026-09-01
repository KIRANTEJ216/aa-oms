"use client";

import { useEffect, useState } from "react";
import { CredentialsAPI, ClientsAPI, type Credential, type CredentialReveal, type AccessLog, type Client } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound, Eye, EyeOff, Plus, RefreshCw, Trash2, Edit, ShieldCheck, Activity, AlertTriangle } from "lucide-react";

export default function CredentialsPage() {
  const [creds, setCreds] = useState<Credential[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [revealData, setRevealData] = useState<CredentialReveal | null>(null);

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const [c, cl, l] = await Promise.all([
        CredentialsAPI.list(),
        ClientsAPI.list().catch(() => []),
        CredentialsAPI.accessLogs(),
      ]);
      setCreds(c);
      setClients(cl);
      setLogs(l);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, []);

  async function reveal(id: string) {
    try {
      const r = await CredentialsAPI.reveal(id);
      setRevealData(r);
      await refresh();
    } catch (e: any) { setError(e.message); }
  }

  async function deleteCred(id: string) {
    if (!confirm("Delete this credential? This action cannot be undone (audit log retained).")) return;
    try {
      await CredentialsAPI.remove(id);
      await refresh();
    } catch (e: any) { setError(e.message); }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <KeyRound className="h-5 w-5" /> Credential Vault
          </h1>
          <p className="text-sm text-slate-500">AES-256-GCM encrypted · every reveal is audit-logged</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
          <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4 mr-1" /> Add Credential</Button>
        </div>
      </div>

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}

      {/* Security notice */}
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="pt-4 flex items-start gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800">
            <p className="font-medium">Confidentiality Notice</p>
            <p>Passwords are encrypted with AES-256-GCM at rest. Every reveal request is logged immutably in <code className="bg-amber-100 px-1 rounded">credentialAccessLogs</code> and the global audit trail. Only Admin / Partner / Manager roles can view or reveal.</p>
          </div>
        </CardContent>
      </Card>

      {/* Vault list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Stored Credentials ({creds.length})</CardTitle>
          <CardDescription>Passwords never displayed in list — only on explicit reveal action</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[820px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Client</th>
                <th className="text-left p-3">URL</th>
                <th className="text-left p-3">Username</th>
                <th className="text-left p-3">Last accessed</th>
                <th className="text-left p-3">Accesses</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {creds.map(c => {
                const cName = clients.find(cl => cl.id === c.client_id)?.name;
                return (
                  <tr key={c.id} className="border-b hover:bg-slate-50">
                    <td className="p-3 font-medium">{c.name}</td>
                    <td className="p-3 text-slate-600">{cName || "—"}</td>
                    <td className="p-3 text-slate-500 text-xs max-w-[180px] truncate">{c.url || "—"}</td>
                    <td className="p-3 font-mono text-xs">{c.username_masked}</td>
                    <td className="p-3 text-slate-500 text-xs">{c.last_accessed_at ? c.last_accessed_at.slice(0, 16).replace("T", " ") : "never"}</td>
                    <td className="p-3 text-slate-600">{c.access_count}</td>
                    <td className="p-3 text-right space-x-1">
                      <Button variant="outline" size="sm" onClick={() => reveal(c.id)} title="Reveal password">
                        <Eye className="h-3 w-3" />
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setEditingId(c.id)} title="Edit">
                        <Edit className="h-3 w-3" />
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => deleteCred(c.id)} title="Delete">
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
              {creds.length === 0 && !loading && (
                <tr><td colSpan={7} className="p-6 text-center text-slate-400 italic">No credentials stored yet. Add one to get started.</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </CardContent>
      </Card>

      {/* Access logs */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2"><Activity className="h-4 w-4" /> Access Log</CardTitle>
          <CardDescription>Every reveal/creation/update of a credential</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">When</th>
                <th className="text-left p-3">Action</th>
                <th className="text-left p-3">Credential</th>
                <th className="text-left p-3">Actor</th>
              </tr>
            </thead>
            <tbody>
              {logs.slice(0, 20).map(l => (
                <tr key={l.id} className="border-b">
                  <td className="p-3 text-slate-500 text-xs font-mono whitespace-nowrap">{l.accessed_at.slice(0, 19).replace("T", " ")}</td>
                  <td className="p-3">
                    <span className={`rounded text-xs px-2 py-0.5 ${l.action === "REVEAL" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-700"}`}>{l.action}</span>
                  </td>
                  <td className="p-3 font-medium">{l.credential_name}</td>
                  <td className="p-3 text-slate-500 text-xs">{l.actor_id}</td>
                </tr>
              ))}
              {logs.length === 0 && !loading && (
                <tr><td colSpan={4} className="p-6 text-center text-slate-400 italic">No access events yet.</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-slate-500">Loading vault…</p>}

      {showCreate && <CredentialDialog clients={clients} onClose={() => setShowCreate(false)} onSaved={refresh} />}
      {editingId && <CredentialDialog clients={clients} editId={editingId} existing={creds.find(c => c.id === editingId)} onClose={() => setEditingId(null)} onSaved={refresh} />}
      {revealData && <RevealModal data={revealData} onClose={() => setRevealData(null)} />}
    </div>
  );
}

function CredentialDialog({ clients, editId, existing, onClose, onSaved }: { clients: Client[]; editId?: string; existing?: Credential; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: existing?.name || "",
    client_id: existing?.client_id || "",
    url: existing?.url || "",
    username: "",
    password: "",
    notes: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setSaving(true);
    try {
      if (editId) {
        // PATCH — only send changed fields
        const data: any = {};
        if (form.name !== existing?.name) data.name = form.name;
        if (form.client_id !== existing?.client_id) data.client_id = form.client_id || undefined;
        if (form.url !== existing?.url) data.url = form.url || undefined;
        if (form.username) data.username = form.username;
        if (form.password) data.password = form.password;
        if (form.notes) data.notes = form.notes;
        await CredentialsAPI.update(editId, data);
      } else {
        await CredentialsAPI.create({
          name: form.name, client_id: form.client_id || undefined, url: form.url || undefined,
          username: form.username, password: form.password, notes: form.notes || undefined,
        });
      }
      onSaved();
      onClose();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>{editId ? "Edit" : "Add"} Credential</CardTitle>
          <CardDescription>{editId ? "Leave username/password blank to keep existing" : "Stored with AES-256-GCM encryption"}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <div><Label>Name (e.g., “GST Portal”, “IT e-Filing Admin”)</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} required /></div>
            <div><Label>Client (optional)</Label>
              <select value={form.client_id} onChange={e => setForm({...form, client_id: e.target.value})} className="w-full h-10 rounded-md border px-2 text-sm">
                <option value="">— None —</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name} ({c.pan})</option>)}
              </select>
            </div>
            <div><Label>URL (optional)</Label><Input value={form.url} onChange={e => setForm({...form, url: e.target.value})} placeholder="https://..." /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Username {editId && "(leave blank to keep)"}</Label><Input value={form.username} onChange={e => setForm({...form, username: e.target.value})} autoComplete="off" /></div>
              <div><Label>Password {editId && "(leave blank to keep)"}</Label><Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} autoComplete="new-password" /></div>
            </div>
            <div><Label>Notes</Label><Input value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} placeholder="TOTP seed, backup account, etc." /></div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving…" : editId ? "Update" : "Add"}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function RevealModal({ data, onClose }: { data: CredentialReveal; onClose: () => void }) {
  const [showPassword, setShowPassword] = useState(false);
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <Card className="w-full max-w-md" onClick={e => e.stopPropagation()}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Reveal Credential</CardTitle>
          <CardDescription className="text-amber-700">⚠ This action is audit-logged</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label>Name</Label>
            <Input value={data.name} readOnly />
          </div>
          <div>
            <Label>Username</Label>
            <Input value={data.username} readOnly />
          </div>
          <div>
            <Label>Password</Label>
            <div className="flex gap-2">
              <Input type={showPassword ? "text" : "password"} value={data.password} readOnly className="font-mono" />
              <Button variant="outline" onClick={() => setShowPassword(!showPassword)}>
                {showPassword ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
              </Button>
              <Button variant="outline" onClick={() => navigator.clipboard?.writeText(data.password)}>Copy</Button>
            </div>
          </div>
          {data.url && <div><Label>URL</Label><Input value={data.url} readOnly /></div>}
          {data.notes && <div><Label>Notes</Label><Input value={data.notes} readOnly /></div>}
          <p className="text-xs text-slate-500">Revealed at {data.revealed_at.slice(0, 19).replace("T", " ")}</p>
          <div className="flex justify-end">
            <Button variant="outline" onClick={onClose}>Close</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
