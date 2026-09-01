"use client";

import { useEffect, useState } from "react";
import { ReportsAPI, type AgingDetail, type RevenueByClientRow, type RevenueByServiceRow, type GstLiability, type MonthlyMIS } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCw, TrendingUp, Users, Layers, Landmark, BarChart3 } from "lucide-react";

const fmt = (n: number) => "₹" + (n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const AGEING_COLORS: Record<string, string> = {
  "0-30": "bg-green-50 text-green-700",
  "31-60": "bg-amber-50 text-amber-700",
  "61-90": "bg-orange-50 text-orange-700",
  "90+": "bg-red-50 text-red-700",
};

export default function ReportsPage() {
  const [aging, setAging] = useState<AgingDetail | null>(null);
  const [revClient, setRevClient] = useState<{ rows: RevenueByClientRow[]; grand_total: number } | null>(null);
  const [revService, setRevService] = useState<{ rows: RevenueByServiceRow[]; grand_total: number } | null>(null);
  const [gst, setGst] = useState<GstLiability | null>(null);
  const [mis, setMis] = useState<MonthlyMIS | null>(null);
  const [tab, setTab] = useState("aging");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const [a, c, s, g, m] = await Promise.all([
        ReportsAPI.aging(),
        ReportsAPI.revenueByClient(),
        ReportsAPI.revenueByService(),
        ReportsAPI.gstLiability(),
        ReportsAPI.monthlyMIS(),
      ]);
      setAging(a); setRevClient(c); setRevService(s); setGst(g); setMis(m);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, []);

  const tabs = [
    { key: "aging", label: "Receivables Aging", icon: Landmark },
    { key: "client", label: "Revenue by Client", icon: Users },
    { key: "service", label: "Revenue by Service", icon: Layers },
    { key: "gst", label: "GST Liability", icon: TrendingUp },
    { key: "mis", label: "Monthly MIS", icon: BarChart3 },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Reports & Analytics</h1>
          <p className="text-sm text-slate-500">Service-wise & month-wise billing · receivables aging · GST liability</p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 flex-wrap border-b">
        {tabs.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 rounded-t-md border-b-2 px-3 py-2 text-sm transition ${tab === t.key ? "border-slate-900 bg-slate-50 font-medium" : "border-transparent hover:bg-slate-50 text-slate-500"}`}>
              <Icon className="h-4 w-4" /> {t.label}
            </button>
          );
        })}
      </div>

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}
      {loading && <p className="text-sm text-slate-500">Loading reports…</p>}

      {!loading && tab === "aging" && aging && <AgingReport aging={aging} />}
      {!loading && tab === "client" && revClient && <RevenueByClient rows={revClient.rows} grandTotal={revClient.grand_total} />}
      {!loading && tab === "service" && revService && <RevenueByService rows={revService.rows} grandTotal={revService.grand_total} />}
      {!loading && tab === "gst" && gst && <GstReport gst={gst} />}
      {!loading && tab === "mis" && mis && <MISReport mis={mis} />}
    </div>
  );
}

function AgingReport({ aging }: { aging: AgingDetail }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        {Object.entries(aging.summary).map(([k, v]) => (
          <Card key={k} className={AGEING_COLORS[k]}>
            <CardContent className="pt-6">
              <p className="text-xs opacity-70">{k} days</p>
              <p className="text-2xl font-bold">{fmt(v.amount)}</p>
              <p className="text-xs opacity-70">{v.count} invoice{v.count !== 1 ? "s" : ""}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Outstanding Invoices by Aging Bucket</CardTitle>
          <CardDescription>Total receivable locked in overdue invoices: {fmt(aging.total_outstanding)} across {aging.total_invoices} invoices</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm min-w-[640px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">Bucket</th>
                <th className="text-left p-3">Invoice</th>
                <th className="text-left p-3">Client</th>
                <th className="text-left p-3">Due date</th>
                <th className="text-right p-3">Outstanding</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(aging.detail).flatMap(([key, v]) =>
                v.invoices.map(inv => (
                  <tr key={inv.id} className="border-b hover:bg-slate-50">
                    <td className="p-3"><span className={`rounded-full px-2 py-0.5 text-xs ${AGEING_COLORS[key]}`}>{key}</span></td>
                    <td className="p-3 font-medium">{inv.invoice_number}</td>
                    <td className="p-3">{inv.client_name}</td>
                    <td className="p-3 text-slate-500">{inv.due_date}</td>
                    <td className="p-3 text-right font-medium">{fmt(inv.outstanding)}</td>
                  </tr>
                ))
              )}
              {aging.total_invoices === 0 && <tr><td colSpan={5} className="p-6 text-center text-slate-400 italic">No overdue receivables — all invoices settled on time 🎉</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function RevenueByClient({ rows, grandTotal }: { rows: RevenueByClientRow[]; grandTotal: number }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Revenue by Client</CardTitle>
        <CardDescription>Billed, collected and outstanding across all invoices · Grand total billed {fmt(grandTotal)}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-slate-50 border-b">
            <tr>
              <th className="text-left p-3">Client</th>
              <th className="text-right p-3">Invoices</th>
              <th className="text-right p-3">Billed</th>
              <th className="text-right p-3">Collected</th>
              <th className="text-right p-3">Outstanding</th>
              <th className="text-right p-3">Collection</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.client_id} className="border-b hover:bg-slate-50">
                <td className="p-3 font-medium">{r.client_name}</td>
                <td className="p-3 text-right text-slate-500">{r.invoice_count}</td>
                <td className="p-3 text-right">{fmt(r.billed)}</td>
                <td className="p-3 text-right text-green-700">{fmt(r.collected)}</td>
                <td className="p-3 text-right text-amber-700">{fmt(r.outstanding)}</td>
                <td className="p-3 text-right text-slate-600">{r.billed ? Math.round(r.collected / r.billed * 100) : 0}%</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-slate-400 italic">No invoices yet.</td></tr>}
          </tbody>
          <tfoot className="bg-slate-50">
            <tr>
              <td className="p-3 font-semibold">Total</td>
              <td className="p-3 text-right font-semibold">{rows.reduce((s, r) => s + r.invoice_count, 0)}</td>
              <td className="p-3 text-right font-semibold">{fmt(rows.reduce((s, r) => s + r.billed, 0))}</td>
              <td className="p-3 text-right font-semibold">{fmt(rows.reduce((s, r) => s + r.collected, 0))}</td>
              <td className="p-3 text-right font-semibold">{fmt(rows.reduce((s, r) => s + r.outstanding, 0))}</td>
              <td className="p-3"></td>
            </tr>
          </tfoot>
        </table>
      </CardContent>
    </Card>
  );
}

function RevenueByService({ rows, grandTotal }: { rows: RevenueByServiceRow[]; grandTotal: number }) {
  const max = Math.max(...rows.map(r => r.amount), 0);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Revenue by Service</CardTitle>
        <CardDescription>Fee income grouped by service/SAC code · Grand total {fmt(grandTotal)}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-slate-50 border-b">
            <tr>
              <th className="text-left p-3">Service</th>
              <th className="text-left p-3">SAC</th>
              <th className="text-left p-3 w-1/4">Share</th>
              <th className="text-right p-3">Invoices</th>
              <th className="text-right p-3">Fees (excl GST)</th>
              <th className="text-right p-3">GST</th>
              <th className="text-right p-3">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b hover:bg-slate-50">
                <td className="p-3 font-medium">{r.service}</td>
                <td className="p-3 font-mono text-xs">{r.sac_code || "—"}</td>
                <td className="p-3">
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden w-full">
                    <div className="h-full bg-blue-600" style={{ width: `${max ? Math.round(r.amount / max * 100) : 0}%` }} />
                  </div>
                </td>
                <td className="p-3 text-right text-slate-500">{r.invoice_count}</td>
                <td className="p-3 text-right">{fmt(r.amount)}</td>
                <td className="p-3 text-right text-slate-500">{fmt(r.gst)}</td>
                <td className="p-3 text-right font-medium">{fmt(r.total)}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-slate-400 italic">No invoices yet.</td></tr>}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function GstReport({ gst }: { gst: GstLiability }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">CGST</p><p className="text-2xl font-bold">{fmt(gst.totals.cgst)}</p></CardContent></Card>
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">SGST</p><p className="text-2xl font-bold">{fmt(gst.totals.sgst)}</p></CardContent></Card>
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">IGST</p><p className="text-2xl font-bold">{fmt(gst.totals.igst)}</p></CardContent></Card>
        <Card className="bg-blue-50"><CardContent className="pt-6"><p className="text-xs text-blue-700">Total GST liability</p><p className="text-2xl font-bold">{fmt(gst.totals.total)}</p></CardContent></Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Monthly GST Liability</CardTitle>
          <CardDescription>Tax component per invoice month (CGST+SGST for intra-state, IGST for inter-state)</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm min-w-[560px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">Month</th>
                <th className="text-right p-3">CGST</th>
                <th className="text-right p-3">SGST</th>
                <th className="text-right p-3">IGST</th>
                <th className="text-right p-3">Total</th>
                <th className="text-right p-3">Invoices</th>
              </tr>
            </thead>
            <tbody>
              {gst.monthly.map(m => (
                <tr key={m.month} className="border-b hover:bg-slate-50">
                  <td className="p-3 font-medium">{m.month}</td>
                  <td className="p-3 text-right">{fmt(m.cgst)}</td>
                  <td className="p-3 text-right">{fmt(m.sgst)}</td>
                  <td className="p-3 text-right">{fmt(m.igst)}</td>
                  <td className="p-3 text-right font-medium">{fmt(m.total)}</td>
                  <td className="p-3 text-right text-slate-500">{m.invoice_count}</td>
                </tr>
              ))}
              {gst.monthly.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-slate-400 italic">No invoice data yet.</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function MISReport({ mis }: { mis: MonthlyMIS }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Total billed</p><p className="text-2xl font-bold">{fmt(mis.totals.billed)}</p></CardContent></Card>
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Total collected</p><p className="text-2xl font-bold">{fmt(mis.totals.collected)}</p></CardContent></Card>
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Outstanding</p><p className="text-2xl font-bold">{fmt(mis.totals.outstanding)}</p></CardContent></Card>
        <Card className="bg-green-50"><CardContent className="pt-6"><p className="text-xs text-green-700">Collection rate</p><p className="text-2xl font-bold">{mis.totals.collection_rate}%</p></CardContent></Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Monthly MIS — Invoiced vs Collected</CardTitle>
          <CardDescription>Service-wise / month-wise billing summary (doc §5.6)</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm min-w-[640px]">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left p-3">Month</th>
                <th className="text-right p-3">Invoices</th>
                <th className="text-right p-3">Billed</th>
                <th className="text-right p-3">Collected</th>
                <th className="text-right p-3">Outstanding</th>
                <th className="text-right p-3">Collection %</th>
              </tr>
            </thead>
            <tbody>
              {mis.rows.map(r => (
                <tr key={r.month} className="border-b hover:bg-slate-50">
                  <td className="p-3 font-medium">{r.month}</td>
                  <td className="p-3 text-right text-slate-500">{r.invoice_count}</td>
                  <td className="p-3 text-right">{fmt(r.billed)}</td>
                  <td className="p-3 text-right text-green-700">{fmt(r.collected)}</td>
                  <td className="p-3 text-right text-amber-700">{fmt(r.outstanding)}</td>
                  <td className="p-3 text-right">{r.collection_rate}%</td>
                </tr>
              ))}
              {mis.rows.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-slate-400 italic">No invoice data yet.</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}