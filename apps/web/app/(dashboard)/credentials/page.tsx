"use client";

import { useEffect, useState } from "react";
import { CredentialsAPI, ClientsAPI, type Credential, type CredentialReveal, type AccessLog, type Client, type PortalInfo, type ClientChecklist, type ClientChecklistEntry } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound, Eye, EyeOff, Plus, RefreshCw, Trash2, Edit, ShieldCheck, Activity, AlertTriangle, CheckCircle2, ListChecks } from "lucide-react";

export default function CredentialsPage() {
  const [creds, setCreds] = useState<Credential[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [portals, setPortals] = useState<PortalInfo[]>([]);
  const [checklist, setChecklist] = useState<ClientChecklist | null>(null);
  const [checklistClient, setChecklistClient] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [revealData, setRevealData] = useState<CredentialReveal | null>(null);
  const [prefill, setPrefill] = useState<{ portal?: string; client_id?: string } | null>(null);

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const [c, cl, l, p] = await Promise.all([
        CredentialsAPI.list(),
        ClientsAPI.list().catch(() => []),
        CredentialsAPI.accessLogs(),
        CredentialsAPI.portals().catch(() => ({ portals: [] as PortalInfo[], default_expire_days: 30 })),
      ]);
      setCreds(c);
      setClients(cl);
      setLogs(l);
      setPortals(p.portals);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, []);

  async function loadChecklist(clientId: string) {
    setChecklistClient(clientId);
    if (!clientId) { setChecklist(null); return; }
    try {
      setChecklist(await CredentialsAPI.checklist(clientId));
    } catch (e: any) { setError(e.message); }
  }

  useEffect(() => {
    if (checklistClient && clients.some(c => c.id === checklistClient)) loadChecklist(checklistClient);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [creds]);

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

  const dueCount = creds.filter(c => c.expiry_status === "expired" || c.expiry_status === "expiring_soon").length;

  function expiryBadge(c: Credential) {
    if (!c.expires_at) return <span className="text-slate-400 text-xs">—</span>;
    const label = c.days_to_expiry !== null && c.days_to_expiry !== undefined && c.days_to_expiry < 0
      ? `overdue ${Math.abs(c.days_to_expiry)}d`
      : c.days_to_expiry !== null && c.days_to_expiry !== undefined && c.days_to_expiry === 0
        ? "due today"
        : c.days_to_expiry !== null && c.days_to_expiry !== undefined ? `in ${c.days_to_expiry}d` : "";
    if (c.expiry_status === "expired") return <span className="rounded bg-red-100 text-red-700 text-xs px-2 py-0.5 whitespace-nowrap">Change due {label}</span>;
    if (c.expiry_status === "expiring_soon") return <span className="rounded bg-amber-100 text-amber-800 text-xs px-2 py-0.5 whitespace-nowrap">Change due {label}</span>;
    return <span className="text-xs text-slate-500 whitespace-nowrap">{c.expires_at.slice(0, 10)}</span>;
  }

  function openCollect(e: ClientChecklistEntry) {
    setPrefill({ portal: e.portal, client_id: checklistClient });
    setShowCreate(true);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <KeyRound className="h-5 w-5" /> Credential Vault
          </h1>
          <p className="text-sm text-slate-500">AES-256-GCM encrypted · every reveal is audit-logged · portal password checklist</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
          <Button onClick={() => { setPrefill(null); setShowCreate(true); }}><Plus className="h-4 w-4 mr-1" /> Add Credential</Button>
        </div>
      </div>

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}

      {/* Security + expiry notice */}
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="pt-4 flex items-start gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800 flex-1">
            <p className="font-medium">Confidentiality Notice</p>
            <p>Passwords are encrypted with AES-256-GCM at rest. Every reveal request is logged immutably in <code className="bg-amber-100 px-1 rounded">credentialAccessLogs</code> and the global audit trail. Only Admin / Partner / Manager roles can view or reveal.</p>
            {dueCount > 0 && <p className="mt-1 font-medium">🔑 {dueCount} password{dueCount > 1 ? "s are" : " is"} due for change — see “Change due” badges below.</p>}
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
          <table className="w-full text-sm min-w-[980px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Portal</th>
                <th className="text-left p-3">Client</th>
                <th className="text-left p-3">Username</th>
                <th className="text-left p-3">Expiry</th>
                <th className="text-left p-3">Last accessed</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {creds.map(c => {
                const cName = clients.find(cl => cl.id === c.client_id)?.name;
                return (
                  <tr key={c.id} className="border-b hover:bg-slate-50">
                    <td className="p-3 font-medium">{c.name}</td>
                    <td className="p-3">{c.portal_label ? <span className="rounded bg-slate-100 text-slate-700 text-xs px-2 py-0.5 whitespace-nowrap">{c.portal_label}</span> : <span className="text-slate-400 text-xs">—</span>}</td>
                    <td className="p-3 text-slate-600">{cName || "—"}</td>
                    <td className="p-3 font-mono text-xs">{c.username_masked}</td>
                    <td className="p-3">{expiryBadge(c)}</td>
                    <td className="p-3 text-slate-500 text-xs whitespace-nowrap">{c.last_accessed_at ? c.last_accessed_at.slice(0, 16).replace("T", " ") : "never"}</td>
                    <td className="p-3 text-right space-x-1 whitespace-nowrap">
                      <Button variant="outline" size="sm" onClick={() => reveal(c.id)} title="Reveal password">
                        <Eye className="h-3 w-3" />
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => { setPrefill(null); setEditingId(c.id); }} title="Edit">
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

      {/* Per-client password checklist */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2"><ListChecks className="h-4 w-4" /> Client Password Checklist</CardTitle>
          <CardDescription>Which portal passwords are collected vs still pending from the client</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <select value={checklistClient} onChange={e => loadChecklist(e.target.value)} className="h-9 rounded-md border px-2 text-sm min-w-[220px]">
              <option value="">— Select a client —</option>
              {clients.map(c => <option key={c.id} value={c.id}>{c.name} ({c.pan})</option>)}
            </select>
            {checklist && (
              <div className="flex items-center gap-2 text-xs">
                <span className="rounded bg-green-100 text-green-700 px-2 py-1">✓ {checklist.collected_count} collected</span>
                <span className="rounded bg-slate-100 text-slate-600 px-2 py-1">Pending {checklist.pending_count} / {checklist.total}</span>
              </div>
            )}
          </div>

          {checklist ? (
            <div className="grid gap-2 md:grid-cols-2">
              {checklist.portals.map(e => (
                <div key={e.portal} className={`border rounded p-3 text-sm ${e.collected ? "border-slate-200" : "border-dashed border-slate-300 bg-slate-50"}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium flex items-center gap-1.5">
                        {e.collected ? <CheckCircle2 className="h-4 w-4 text-green-600" /> : <span className="h-4 w-4 rounded-full border border-slate-400 inline-block" />}
                        {e.label}
                      </p>
                      {e.url && <a href={e.url.startsWith("http") ? e.url : `https://${e.url}`} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline">{e.url.replace(/^https?:\/\//, "")}</a>}
                      <p className="text-xs text-slate-400 mt-0.5">{e.expiry_hint}</p>
                      {e.collected && (
                        <p className="text-xs text-slate-500 mt-1">
                          {e.count} credential{e.count > 1 ? "s" : ""}: {e.credentials.map(c => `${c.name} (${c.username_masked})`).join(", ")}
                          {e.credentials.some(c => c.expiry_status === "expired" || c.expiry_status === "expiring_soon") && <span className="text-amber-700 font-medium"> · change due</span>}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1 shrink-0">
                      {e.collected ? (
                        e.credentials.map(c => (
                          <Button key={c.id} variant="outline" size="sm" onClick={() => reveal(c.id)} title="Reveal"><Eye className="h-3 w-3" /></Button>
                        ))
                      ) : (
                        <Button size="sm" onClick={() => openCollect(e)}>Collect</Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 italic">Select a client to see the collected-vs-pending password checklist across the {portals.length || 15} statutory portals (ITS, GST, EPFO, ESIC, PT, ROC…).</p>
          )}
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

      {showCreate && <CredentialDialog clients={clients} portals={portals} initialPortal={prefill?.portal} initialClientId={prefill?.client_id || undefined} onClose={() => { setShowCreate(false); setPrefill(null); }} onSaved={refresh} />}
      {editingId && <CredentialDialog clients={clients} portals={portals} editId={editingId} existing={creds.find(c => c.id === editingId)} onClose={() => setEditingId(null)} onSaved={refresh} />}
      {revealData && <RevealModal data={revealData} onClose={() => setRevealData(null)} />}
    </div>
  );
}

function CredentialDialog({ clients, portals, editId, existing, initialPortal, initialClientId, onClose, onSaved }: { clients: Client[]; portals: PortalInfo[]; editId?: string; existing?: Credential; initialPortal?: string; initialClientId?: string; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    portal: existing?.portal || initialPortal || "",
    name: existing?.name || (initialPortal ? portals.find(p => p.key === initialPortal)?.label || "" : ""),
    client_id: existing?.client_id || initialClientId || "",
    url: existing?.url || "",
    username: "",
    password: "",
    notes: "",
    expires_at: existing?.expires_at || "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const selectedPortal = portals.find(p => p.key === form.portal);
  const defaultExpire = "2027-03-31";

  function setPortal(portal: string) {
    const p = portals.find(x => x.key === portal);
    setForm(f => ({
      ...f,
      portal,
      name: f.name || (p?.label || ""),
      url: f.url || (p?.url || ""),
      expires_at: f.expires_at || defaultExpire,
    }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setSaving(true);
    try {
      if (editId) {
        // PATCH — only send changed fields
        const data: any = {};
        if (form.portal !== (existing?.portal || "")) data.portal = form.portal || undefined;
        if (form.name !== existing?.name) data.name = form.name;
        if (form.client_id !== (existing?.client_id || "")) data.client_id = form.client_id || undefined;
        if (form.url !== (existing?.url || "")) data.url = form.url || undefined;
        if (form.username) data.username = form.username;
        if (form.password) data.password = form.password;
        if (form.notes) data.notes = form.notes;
        if (form.expires_at !== (existing?.expires_at || "")) data.expires_at = form.expires_at || null;
        await CredentialsAPI.update(editId, data);
      } else {
        await CredentialsAPI.create({
          name: form.name, client_id: form.client_id || undefined, portal: form.portal || undefined,
          url: form.url || undefined, username: form.username, password: form.password,
          notes: form.notes || undefined, expires_at: form.expires_at || undefined,
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
            <div>
              <Label>Portal (optional)</Label>
              <select value={form.portal} onChange={e => setPortal(e.target.value)} className="w-full h-10 rounded-md border px-2 text-sm">
                <option value="">— None / custom —</option>
                {portals.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
              </select>
              {selectedPortal && <p className="text-xs text-slate-400 mt-1">{selectedPortal.expiry_hint}</p>}
            </div>
            <div><Label>Name</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder={selectedPortal ? selectedPortal.label : "e.g. GST Portal"} required /></div>
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
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Password change due (optional)</Label><Input type="date" value={form.expires_at} onChange={e => setForm({...form, expires_at: e.target.value})} /></div>
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
          {data.expires_at && <div><Label>Password change due</Label><Input value={data.expires_at.slice(0, 10)} readOnly /></div>}
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