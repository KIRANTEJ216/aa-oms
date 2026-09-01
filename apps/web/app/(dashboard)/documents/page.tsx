"use client";

import { useEffect, useState, useRef } from "react";
import { DocumentsAPI, ClientsAPI, fileToBase64, type Client, type DocFolder, type DocumentItem, type DocumentVersion, type DocumentShare } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Files, Folder, Upload, History, Share2, Trash2, RefreshCw, FolderPlus } from "lucide-react";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export default function DocumentsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState<string>("");
  const [folders, setFolders] = useState<DocFolder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [versionsDocId, setVersionsDocId] = useState<string | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function loadClients() {
    try {
      const c = await ClientsAPI.list();
      setClients(c);
      if (c.length > 0 && !selectedClient) setSelectedClient(c[0].id);
    } catch (e: any) { setError(e.message); }
  }

  async function loadFolders() {
    if (!selectedClient) return;
    try {
      const f = await DocumentsAPI.folders(selectedClient);
      setFolders(f);
      if (f.length > 0 && !selectedFolder) setSelectedFolder(f[0].id);
    } catch (e: any) { setError(e.message); }
  }

  async function loadDocs() {
    if (!selectedClient) return;
    setLoading(true);
    try {
      const d = await DocumentsAPI.listByClient(selectedClient, selectedFolder || undefined);
      setDocs(d);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { loadClients(); }, []);
  useEffect(() => { if (selectedClient) { loadFolders(); setSelectedFolder(""); } }, [selectedClient]);
  useEffect(() => { if (selectedClient) loadDocs(); }, [selectedClient, selectedFolder]);

  async function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!fileInput.current?.files?.[0] || !selectedClient || !selectedFolder) return;
    setUploading(true); setError(null);
    try {
      const file = fileInput.current.files[0];
      if (file.size > 50 * 1024 * 1024) {
        setError(`File too large (${formatBytes(file.size)}). Max 50MB.`);
        setUploading(false);
        return;
      }
      const b64 = await fileToBase64(file);
      await DocumentsAPI.upload({
        client_id: selectedClient, folder_id: selectedFolder,
        name: file.name, content_base64: b64, content_type: file.type,
        tags: [], notes: "",
      });
      fileInput.current.value = "";
      await loadDocs();
    } catch (e: any) { setError(e.message); }
    finally { setUploading(false); }
  }

  async function showVersions(docId: string) {
    try {
      const v = await DocumentsAPI.versions(docId);
      setVersions(v);
      setVersionsDocId(docId);
    } catch (e: any) { setError(e.message); }
  }

  async function uploadNewVersion(docId: string, file: File) {
    try {
      if (file.size > 50 * 1024 * 1024) { setError(`Max 50MB`); return; }
      const b64 = await fileToBase64(file);
      await DocumentsAPI.uploadVersion(docId, b64, file.type, "Re-uploaded from UI");
      const v = await DocumentsAPI.versions(docId);
      setVersions(v);
      await loadDocs();
    } catch (e: any) { setError(e.message); }
  }

  async function createShare(docId: string) {
    try {
      const s = await DocumentsAPI.share(docId, "View Only", 7);
      setShareUrl(`${window.location.origin}${s.share_url}`);
      await loadDocs();
    } catch (e: any) { setError(e.message); }
  }

  async function deleteDoc(docId: string) {
    if (!confirm("Delete this document?")) return;
    try {
      await DocumentsAPI.remove(docId);
      await loadDocs();
    } catch (e: any) { setError(e.message); }
  }

  async function addFolder() {
    const name = prompt("New folder name (e.g., 'Old Returns'):");
    if (!name || !selectedClient) return;
    try {
      await DocumentsAPI.createFolder(selectedClient, name);
      await loadFolders();
    } catch (e: any) { setError(e.message); }
  }

  const currentClient = clients.find(c => c.id === selectedClient);
  const currentFolder = folders.find(f => f.id === selectedFolder);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Documents</h1>
          <p className="text-sm text-slate-500">7 folders per client · versioned · AES-256 at rest</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { loadClients(); loadFolders(); loadDocs(); }}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}

      {/* Client + Folder selection */}
      <Card>
        <CardContent className="pt-6 grid gap-4 md:grid-cols-2">
          <div>
            <Label>Client</Label>
            <select value={selectedClient} onChange={e => setSelectedClient(e.target.value)} className="w-full h-10 rounded-md border px-2 text-sm">
              <option value="">— Select client —</option>
              {clients.map(c => <option key={c.id} value={c.id}>{c.name} ({c.pan})</option>)}
            </select>
            {currentClient && <p className="text-xs text-slate-500 mt-1">{currentClient.gstin || currentClient.pan}</p>}
          </div>
          <div>
            <div className="flex items-center justify-between">
              <Label>Folders (auto-created on first access)</Label>
              {selectedClient && <button onClick={addFolder} className="text-xs text-blue-600 hover:underline flex items-center gap-1"><FolderPlus className="h-3 w-3" /> New</button>}
            </div>
            <div className="grid grid-cols-2 gap-2 mt-2">
              {folders.map(f => (
                <button key={f.id} onClick={() => setSelectedFolder(f.id)}
                  className={`text-left text-sm rounded-md border p-2 transition ${selectedFolder === f.id ? "bg-slate-900 text-white border-slate-900" : "bg-white hover:bg-slate-50"}`}>
                  <Folder className="h-3 w-3 inline mr-1" /> {f.name}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Upload zone */}
      {selectedFolder && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Upload className="h-4 w-4" /> Upload to “{currentFolder?.name}”
            </CardTitle>
            <CardDescription>Max 50MB · versioned automatically (v1, v2, ...)</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUpload} className="flex gap-2 items-end">
              <div className="flex-1">
                <Input ref={fileInput} type="file" required />
              </div>
              <Button type="submit" disabled={uploading}>
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Document list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Documents ({docs.length})</CardTitle>
          <CardDescription>Click a doc for actions (versions, share, delete)</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[760px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Version</th>
                <th className="text-left p-3">Size</th>
                <th className="text-left p-3">Tags</th>
                <th className="text-left p-3">Uploaded</th>
                <th className="text-left p-3">Shared</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map(d => (
                <tr key={d.id} className="border-b hover:bg-slate-50">
                  <td className="p-3 font-medium"><Files className="h-3 w-3 inline mr-1" /> {d.name}</td>
                  <td className="p-3 text-slate-600">v{d.version}</td>
                  <td className="p-3 text-slate-600">{formatBytes(d.size)}</td>
                  <td className="p-3 text-xs text-slate-500">{d.tags.map(t => <span key={t} className="rounded bg-slate-100 px-1.5 py-0.5 mr-1">{t}</span>)}</td>
                  <td className="p-3 text-slate-500 text-xs">{d.created_at.slice(0, 10)}</td>
                  <td className="p-3">{d.is_shared ? <span className="rounded bg-blue-100 text-blue-700 text-xs px-2 py-0.5">{d.share_mode}</span> : <span className="text-xs text-slate-400">—</span>}</td>
                  <td className="p-3 text-right space-x-1">
                    <Button variant="outline" size="sm" onClick={() => showVersions(d.id)}><History className="h-3 w-3" /></Button>
                    <Button variant="outline" size="sm" onClick={() => createShare(d.id)}><Share2 className="h-3 w-3" /></Button>
                    <Button variant="outline" size="sm" onClick={() => deleteDoc(d.id)}><Trash2 className="h-3 w-3" /></Button>
                  </td>
                </tr>
              ))}
              {docs.length === 0 && !loading && (
                <tr><td colSpan={7} className="p-6 text-center text-slate-400 italic">No documents in this folder yet.</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-slate-500">Loading documents…</p>}

      {/* Versions modal */}
      {versionsDocId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setVersionsDocId(null)}>
          <Card className="w-full max-w-lg" onClick={e => e.stopPropagation()}>
            <CardHeader>
              <CardTitle>Version History</CardTitle>
              <CardDescription>All versions are retained</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center gap-2">
                <Input id="new-version-file" type="file" />
                <Button onClick={() => {
                  const input = document.getElementById("new-version-file") as HTMLInputElement;
                  if (input.files?.[0]) uploadNewVersion(versionsDocId, input.files[0]);
                }}>Upload new version</Button>
              </div>
              <ul className="space-y-1 mt-3">
                {versions.sort((a,b)=>b.version-a.version).map(v => (
                  <li key={v.version} className="text-sm border-b pb-2">
                    <p className="font-medium">v{v.version} · {formatBytes(v.size)}</p>
                    <p className="text-xs text-slate-500">{v.uploaded_at} {v.notes && `· ${v.notes}`}</p>
                  </li>
                ))}
              </ul>
              <div className="flex justify-end mt-2">
                <Button variant="outline" onClick={() => setVersionsDocId(null)}>Close</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Share modal */}
      {shareUrl && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setShareUrl(null)}>
          <Card className="w-full max-w-lg" onClick={e => e.stopPropagation()}>
            <CardHeader>
              <CardTitle>Share Link Created</CardTitle>
              <CardDescription>Valid for 7 days · View Only</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-slate-500">Anyone with this link can view the document until it expires:</p>
              <div className="flex gap-2">
                <Input value={shareUrl} readOnly />
                <Button onClick={() => navigator.clipboard?.writeText(shareUrl)}>Copy</Button>
              </div>
              <div className="flex justify-end">
                <Button variant="outline" onClick={() => setShareUrl(null)}>Close</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
