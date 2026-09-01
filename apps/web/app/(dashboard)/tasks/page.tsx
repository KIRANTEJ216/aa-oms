"use client";

import { useEffect, useState } from "react";
import { TasksAPI, ClientsAPI, type Task, type TaskStats, type Client } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertTriangle, Plus, RefreshCw, CheckCircle2, Clock, Filter } from "lucide-react";

const TASK_COLUMNS = [
  { id: "Not Started", label: "Not Started", color: "bg-slate-100 border-slate-300" },
  { id: "In Progress", label: "In Progress", color: "bg-blue-50 border-blue-300" },
  { id: "Pending Information", label: "Pending Info", color: "bg-amber-50 border-amber-300" },
  { id: "Under Review", label: "Under Review", color: "bg-purple-50 border-purple-300" },
  { id: "Completed", label: "Completed", color: "bg-green-50 border-green-300" },
];

const PRIORITY_STYLES: Record<string, string> = {
  High: "bg-red-100 text-red-700",
  Medium: "bg-amber-100 text-amber-700",
  Low: "bg-slate-100 text-slate-700",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<TaskStats | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOverdueOnly, setShowOverdueOnly] = useState(false);
  const [view, setView] = useState<"kanban" | "table">("kanban");
  const [showCreate, setShowCreate] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [t, s, c] = await Promise.all([
        TasksAPI.list(showOverdueOnly ? { overdue_only: true } : undefined),
        TasksAPI.stats(),
        ClientsAPI.list().catch(() => []),
      ]);
      setTasks(t);
      setStats(s);
      setClients(c);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, [showOverdueOnly]);

  async function changeStatus(id: string, status: string) {
    try {
      await TasksAPI.updateStatus(id, status);
      await refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function removeTask(id: string) {
    if (!confirm("Delete this task?")) return;
    try {
      await TasksAPI.remove(id);
      await refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Tasks</h1>
          <p className="text-sm text-slate-500">Statutory · Client · Internal · Recurring</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowOverdueOnly(!showOverdueOnly)}>
            <Filter className="h-4 w-4 mr-1" /> {showOverdueOnly ? "All" : "Overdue only"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setView(view === "kanban" ? "table" : "kanban")}>
            {view === "kanban" ? "Table" : "Kanban"}
          </Button>
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
          <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4 mr-1" /> New Task</Button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid gap-3 md:grid-cols-4">
          <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Total</p><p className="text-2xl font-bold">{stats.total}</p></CardContent></Card>
          <Card className="border-amber-300 bg-amber-50"><CardContent className="pt-6 flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-amber-600" /><div><p className="text-xs text-amber-700">Overdue</p><p className="text-2xl font-bold text-amber-800">{stats.overdue}</p></div></CardContent></Card>
          <Card><CardContent className="pt-6 flex items-center gap-2"><Clock className="h-5 w-5 text-blue-600" /><div><p className="text-xs text-slate-500">Due Today</p><p className="text-2xl font-bold">{stats.due_today}</p></div></CardContent></Card>
          <Card><CardContent className="pt-6 flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-green-600" /><div><p className="text-xs text-slate-500">This Week</p><p className="text-2xl font-bold">{stats.due_this_week}</p></div></CardContent></Card>
        </div>
      )}

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}

      {loading && <p className="text-sm text-slate-500">Loading tasks…</p>}

      {/* Kanban view */}
      {view === "kanban" && !loading && (
        <div className="grid gap-3 md:grid-cols-5">
          {TASK_COLUMNS.map(col => {
            const colTasks = tasks.filter(t => t.status === col.id);
            return (
              <div key={col.id} className={`rounded-lg border p-2 ${col.color}`}>
                <div className="flex items-center justify-between px-1 py-1">
                  <h3 className="text-sm font-semibold">{col.label}</h3>
                  <span className="text-xs text-slate-500">{colTasks.length}</span>
                </div>
                <div className="space-y-2 mt-1">
                  {colTasks.map(t => (
                    <Card key={t.id} className={t.is_overdue ? "border-red-400" : ""}>
                      <CardContent className="p-3 space-y-2">
                        <div className="flex items-start justify-between gap-1">
                          <p className="text-sm font-medium leading-tight">{t.title}</p>
                          {t.is_overdue && <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />}
                        </div>
                        <div className="flex items-center gap-1 text-xs">
                          <span className={`rounded px-1.5 py-0.5 ${PRIORITY_STYLES[t.priority]}`}>{t.priority}</span>
                          <span className="text-slate-500">{t.type}</span>
                        </div>
                        <p className="text-xs text-slate-500">Due: {t.due_date}</p>
                        {t.client_id && (
                          <p className="text-xs text-slate-400">→ {clients.find(c => c.id === t.client_id)?.name || "Client"}</p>
                        )}
                        <div className="flex gap-1 pt-1">
                          {TASK_COLUMNS.filter(c => c.id !== t.status).slice(0, 2).map(c => (
                            <button key={c.id} onClick={() => changeStatus(t.id, c.id)}
                              className="text-[10px] rounded bg-white border px-1 py-0.5 hover:bg-slate-50">{c.label}</button>
                          ))}
                          <button onClick={() => removeTask(t.id)} className="text-[10px] rounded bg-red-50 text-red-600 border border-red-200 px-1 py-0.5 ml-auto hover:bg-red-100">×</button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                  {colTasks.length === 0 && <p className="text-xs text-slate-400 italic text-center py-2">empty</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Table view */}
      {view === "table" && !loading && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[760px]">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="text-left p-3">Title</th>
                  <th className="text-left p-3">Type</th>
                  <th className="text-left p-3">Priority</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-left p-3">Due</th>
                  <th className="text-left p-3">Client</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {tasks.map(t => (
                  <tr key={t.id} className={`border-b hover:bg-slate-50 ${t.is_overdue ? "bg-red-50/40" : ""}`}>
                    <td className="p-3 font-medium">
                      {t.title}
                      {t.is_overdue && <span className="ml-2 text-[10px] rounded bg-red-100 text-red-700 px-1.5">OVERDUE</span>}
                    </td>
                    <td className="p-3 text-slate-600">{t.type}</td>
                    <td className="p-3"><span className={`rounded px-1.5 py-0.5 text-xs ${PRIORITY_STYLES[t.priority]}`}>{t.priority}</span></td>
                    <td className="p-3 text-slate-600">{t.status}</td>
                    <td className="p-3 text-slate-600">{t.due_date}</td>
                    <td className="p-3 text-slate-500 text-xs">{clients.find(c => c.id === t.client_id)?.name || "—"}</td>
                    <td className="p-3 text-right">
                      <Button variant="outline" size="sm" onClick={() => removeTask(t.id)}>×</Button>
                    </td>
                  </tr>
                ))}
                {tasks.length === 0 && (
                  <tr><td colSpan={7} className="p-6 text-center text-slate-400 italic">No tasks yet — click “New Task” to create one.</td></tr>
                )}
              </tbody>
            </table>
            </div>
          </CardContent>
        </Card>
      )}

      {showCreate && <CreateTaskDialog clients={clients} onClose={() => setShowCreate(false)} onCreated={refresh} />}
    </div>
  );
}

function CreateTaskDialog({ clients, onClose, onCreated }: { clients: Client[]; onClose: () => void; onCreated: () => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    type: "Client" as "Statutory" | "Client" | "Internal" | "Recurring",
    title: "",
    description: "",
    priority: "Medium" as "High" | "Medium" | "Low",
    status: "Not Started" as "Not Started" | "In Progress" | "Pending Information" | "Under Review" | "Completed",
    due_date: today,
    client_id: clients[0]?.id || "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setSaving(true);
    try {
      const data: any = { ...form };
      if (!data.client_id) delete data.client_id;
      await TasksAPI.create(data);
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
        <CardHeader><CardTitle>New Task</CardTitle><CardDescription>Create a task and assign it</CardDescription></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Type</Label><select value={form.type} onChange={e => setForm({...form, type: e.target.value as any})} className="w-full h-10 rounded-md border px-2 text-sm"><option>Statutory</option><option>Client</option><option>Internal</option><option>Recurring</option></select></div>
              <div><Label>Priority</Label><select value={form.priority} onChange={e => setForm({...form, priority: e.target.value as any})} className="w-full h-10 rounded-md border px-2 text-sm"><option>High</option><option>Medium</option><option>Low</option></select></div>
            </div>
            <div><Label>Title</Label><Input value={form.title} onChange={e => setForm({...form, title: e.target.value})} required minLength={2} /></div>
            <div><Label>Description</Label><Input value={form.description} onChange={e => setForm({...form, description: e.target.value})} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Due date</Label><Input type="date" value={form.due_date} onChange={e => setForm({...form, due_date: e.target.value})} required /></div>
              <div><Label>Client (optional)</Label>
                <select value={form.client_id} onChange={e => setForm({...form, client_id: e.target.value})} className="w-full h-10 rounded-md border px-2 text-sm">
                  <option value="">— None —</option>
                  {clients.map(c => <option key={c.id} value={c.id}>{c.name} ({c.pan})</option>)}
                </select>
              </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Creating…" : "Create Task"}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
