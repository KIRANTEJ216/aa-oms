"use client";

import { useEffect, useState } from "react";
import { TasksAPI, ComplianceAPI, type TaskStats, type ComplianceHealth } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ClipboardList, CalendarCheck, Receipt, AlertTriangle, ShieldCheck, TrendingUp } from "lucide-react";

const TENANT_MODE = process.env.NEXT_PUBLIC_TENANT_MODE || "single";

export default function DashboardPage() {
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null);
  const [compHealth, setCompHealth] = useState<ComplianceHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      TasksAPI.stats().catch(() => null),
      ComplianceAPI.health().catch(() => null),
    ]).then(([t, c]) => {
      setTaskStats(t);
      setCompHealth(c);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard — Aarav Advisors</h1>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">TENANT_MODE={TENANT_MODE}</span>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading dashboard…</p>}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><ClipboardList className="h-4 w-4"/> My Tasks</CardTitle><CardDescription>Total open</CardDescription></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{taskStats?.total ?? "—"}</p>
            <p className="text-xs text-slate-500">{taskStats?.due_today ?? 0} due today · {taskStats?.due_this_week ?? 0} this week</p>
          </CardContent>
        </Card>
        <Card className="border-red-300 bg-red-50">
          <CardHeader><CardTitle className="flex items-center gap-2 text-sm text-red-700"><AlertTriangle className="h-4 w-4"/> Overdue</CardTitle><CardDescription>Action needed</CardDescription></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-red-800">{taskStats?.overdue ?? "—"}</p>
            <p className="text-xs text-red-600">tasks + {(compHealth?.by_health.Red ?? 0)} compliance filings</p>
          </CardContent>
        </Card>
        <Card className="border-amber-300 bg-amber-50">
          <CardHeader><CardTitle className="flex items-center gap-2 text-sm text-amber-700"><CalendarCheck className="h-4 w-4"/> Compliance</CardTitle><CardDescription>Health dashboard</CardDescription></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-amber-800">{compHealth?.total ?? "—"}</p>
            <p className="text-xs text-amber-600">{compHealth?.by_health.Amber ?? 0} due in 7d · {compHealth?.by_health.Green ?? 0} on track</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><TrendingUp className="h-4 w-4"/> In Progress</CardTitle><CardDescription>Active work</CardDescription></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{taskStats?.by_status?.["In Progress"] ?? "—"}</p>
            <p className="text-xs text-slate-500">+ {taskStats?.by_status?.["Under Review"] ?? 0} under review</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Task status breakdown</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-sm">
            {taskStats && Object.entries(taskStats.by_status).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-slate-600">{k}</span><span className="font-medium">{v}</span>
              </div>
            ))}
            {!taskStats && <p className="text-slate-400 italic">Loading…</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Compliance by code</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-sm">
            {compHealth && Object.keys(compHealth.by_code).length === 0 && <p className="text-slate-400 italic">No compliance filings yet</p>}
            {compHealth && Object.entries(compHealth.by_code).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-slate-600">{k}</span><span className="font-medium">{v}</span>
              </div>
            ))}
            {!compHealth && <p className="text-slate-400 italic">Loading…</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Audit Trail</CardTitle></CardHeader>
          <CardContent>
            <p className="text-xs text-slate-500">Every create/update/delete/login is immutable and timestamped. View at <a href="/audit" className="underline">/audit</a>.</p>
            <p className="text-xs text-slate-500 mt-2">All data isolated by <code className="bg-slate-100 px-1 rounded">tenant_id = aarav-advisors</code></p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Next Steps for Pilot</CardTitle>
          <CardDescription>Add real clients at /clients → create tasks → generate invoices → track compliance</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2 flex-wrap">
          <a href="/clients" className="inline-flex h-10 items-center justify-center rounded-md bg-slate-900 px-4 text-sm font-medium text-white">Go to Clients</a>
          <a href="/tasks" className="inline-flex h-10 items-center justify-center rounded-md border bg-white px-4 text-sm font-medium">Go to Tasks</a>
          <a href="/compliance" className="inline-flex h-10 items-center justify-center rounded-md border bg-white px-4 text-sm font-medium">Go to Compliance</a>
          <a href="/billing" className="inline-flex h-10 items-center justify-center rounded-md border bg-white px-4 text-sm font-medium">Go to Billing</a>
        </CardContent>
      </Card>
    </div>
  );
}
