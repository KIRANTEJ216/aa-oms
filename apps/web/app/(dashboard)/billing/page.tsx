"use client";

import { useEffect, useState } from "react";
import { BillingAPI, ClientsAPI, type Invoice, type AgingReport, type Client } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Receipt, Plus, RefreshCw, Banknote, TrendingUp } from "lucide-react";

const SAC = [
  { code: "998299", desc: "Accounting & Auditing Services" },
  { code: "998212", desc: "Taxation & Compliance Services" },
  { code: "998214", desc: "Business & Management Consulting" },
];

const STATUS_STYLES: Record<string, string> = {
  Unpaid: "bg-amber-100 text-amber-700",
  "Partially Paid": "bg-blue-100 text-blue-700",
  Paid: "bg-green-100 text-green-700",
  Overdue: "bg-red-100 text-red-700",
};

const fmt = (n: number) => "₹" + n.toLocaleString("en-IN");

export default function BillingPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [aging, setAging] = useState<AgingReport | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [payingInvoice, setPayingInvoice] = useState<Invoice | null>(null);

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const [inv, ag, cl] = await Promise.all([
        BillingAPI.list(statusFilter === "all" ? undefined : { status: statusFilter }),
        BillingAPI.aging().catch(() => null),
        ClientsAPI.list().catch(() => []),
      ]);
      setInvoices(inv);
      setAging(ag);
      setClients(cl);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, [statusFilter]);

  const totalReceivable = invoices.reduce((s, i) => s + (i.status === "Paid" ? 0 : i.total), 0);
  const clientName = (id: string) => clients.find(c => c.id === id)?.name || id;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2"><Receipt className="h-6 w-6" /> Billing</h1>
          <p className="text-sm text-slate-500">GST invoices · CGST/SGST vs IGST · payments · aging</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="h-9 rounded-md border px-2 text-sm">
            <option value="all">All statuses</option>
            <option value="Unpaid">Unpaid</option>
            <option value="Partially Paid">Partially Paid</option>
            <option value="Paid">Paid</option>
            <option value="Overdue">Overdue</option>
          </select>
          <Button variant="outline" size="sm" onClick={refresh}><RefreshCw className="h-4 w-4" /></Button>
          <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4 mr-1" /> New Invoice</Button>
        </div>
      </div>

      {error && <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}

      {/* Stats + aging */}
      <div className="grid gap-3 md:grid-cols-4">
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Total receivable</p><p className="text-2xl font-bold">{fmt(totalReceivable)}</p></CardContent></Card>
        <Card><CardContent className="pt-6"><p className="text-xs text-slate-500">Invoices</p><p className="text-2xl font-bold">{invoices.length}</p></CardContent></Card>
        <Card className="border-amber-300 bg-amber-50"><CardContent className="pt-6"><p className="text-xs text-amber-700">Unpaid</p><p className="text-2xl font-bold text-amber-800">{invoices.filter(i => i.status === "Unpaid" || i.status === "Overdue").length}</p></CardContent></Card>
        <Card className="border-green-300 bg-green-50"><CardContent className="pt-6"><p className="text-xs text-green-700">Paid</p><p className="text-2xl font-bold text-green-800">{invoices.filter(i => i.status === "Paid").length}</p></CardContent></Card>
      </div>

      {/* Aging buckets */}
      {aging && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2"><TrendingUp className="h-4 w-4" /> Aging Buckets</CardTitle>
            <CardDescription>Receivables by days overdue</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-3 text-center">
              {Object.entries(aging.buckets).map(([k, v]) => (
                <div key={k} className="rounded-lg border p-3">
                  <p className="text-2xl font-bold">{v}</p>
                  <p className="text-xs text-slate-500">{k} days</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Invoice table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Invoices ({invoices.length})</CardTitle>
          <CardDescription>Click a paid/partial invoice to record a payment</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[760px]">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="text-left p-3">Invoice</th>
                  <th className="text-left p-3">Client</th>
                  <th className="text-left p-3">Type</th>
                  <th className="text-left p-3">GST</th>
                  <th className="text-left p-3">Amount</th>
                  <th className="text-left p-3">Due</th>
                  <th className="text-left p-3">Status</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map(inv => (
                  <tr key={inv.id} className="border-b hover:bg-slate-50">
                    <td className="p-3 font-medium">{inv.invoice_number}</td>
                    <td className="p-3 text-slate-600">{clientName(inv.client_id)}</td>
                    <td className="p-3 text-slate-600">{inv.invoice_type}</td>
                    <td className="p-3 text-xs text-slate-500">{inv.gst_treatment}</td>
                    <td className="p-3 font-medium">{fmt(inv.total)}</td>
                    <td className="p-3 text-slate-600">{inv.due_date}</td>
                    <td className="p-3"><span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLES[inv.status] || "bg-slate-100 text-slate-700"}`}>{inv.status}</span></td>
                    <td className="p-3 text-right">
                      {inv.status !== "Paid" && (
                        <Button variant="outline" size="sm" onClick={() => setPayingInvoice(inv)}><Banknote className="h-3 w-3 mr-1" /> Pay</Button>
                      )}
                    </td>
                  </tr>
                ))}
                {invoices.length === 0 && !loading && (
                  <tr><td colSpan={8} className="p-6 text-center text-slate-400 italic">No invoices yet — click “New Invoice” to create one.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-slate-500">Loading billing…</p>}

      {showCreate && <CreateInvoiceDialog clients={clients} onClose={() => setShowCreate(false)} onCreated={refresh} />}
      {payingInvoice && <PaymentDialog invoice={payingInvoice} onClose={() => setPayingInvoice(null)} onPaid={refresh} />}
    </div>
  );
}

function CreateInvoiceDialog({ clients, onClose, onCreated }: { clients: Client[]; onClose: () => void; onCreated: () => void }) {
  const [clientId, setClientId] = useState(clients[0]?.id || "");
  const [clientState, setClientState] = useState("KA");
  const [items, setItems] = useState<Array<{ description: string; sac_code: string; amount: number; gst_rate: number }>>([
    { description: "Professional fees", sac_code: "998299", amount: 0, gst_rate: 18 },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const base = items.reduce((s, it) => s + (Number(it.amount) || 0), 0);
  const gst = items.reduce((s, it) => s + (Number(it.amount) || 0) * (it.gst_rate || 0) / 100, 0);
  const total = base + gst;

  function updateItem(i: number, patch: Partial<typeof items[0]>) {
    setItems(prev => prev.map((it, idx) => idx === i ? { ...it, ...patch } : it));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) { setError("Select a client"); return; }
    if (items.some(it => (it.amount || 0) <= 0)) { setError("All line items must have a positive amount"); return; }
    setError(null); setSaving(true);
    try {
      const gstTreatment = "IGST";
      const cleaned = items.map(({ description, sac_code, amount, gst_rate }) => ({ description, sac_code, amount: Number(amount), gst_rate }));
      await BillingAPI.create({ client_id: clientId, items: cleaned, due_days: 30, gst_treatment: gstTreatment });
      onCreated();
      onClose();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader><CardTitle>New Invoice</CardTitle><CardDescription>CGST/SGST (intra-state) or IGST (inter-state) auto-computed</CardDescription></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Client</Label>
                <select value={clientId} onChange={e => setClientId(e.target.value)} required className="w-full h-10 rounded-md border px-2 text-sm">
                  <option value="">— Select —</option>
                  {clients.map(c => <option key={c.id} value={c.id}>{c.name} ({c.pan})</option>)}
                </select>
              </div>
              <div><Label>Client GST state (for CGST/SGST)</Label>
                <select value={clientState} onChange={e => setClientState(e.target.value)} className="w-full h-10 rounded-md border px-2 text-sm">
                  <option value="KA">Karnataka (intra-state)</option>
                  <option value="OTHER">Other state (IGST)</option>
                </select>
              </div>
            </div>

            <div>
              <Label>Line items</Label>
              <div className="space-y-2 mt-1">
                {items.map((it, i) => (
                  <div key={i} className="grid grid-cols-12 gap-2">
                    <select value={it.sac_code} onChange={e => updateItem(i, { sac_code: e.target.value })} className="col-span-4 h-9 rounded-md border px-2 text-xs">
                      {SAC.map(s => <option key={s.code} value={s.code}>{s.code} · {s.desc}</option>)}
                    </select>
                    <Input className="col-span-4" value={it.description} onChange={e => updateItem(i, { description: e.target.value })} placeholder="Description" />
                    <Input className="col-span-2" type="number" step="0.01" min="0" value={it.amount} onChange={e => updateItem(i, { amount: Number(e.target.value) })} placeholder="0.00" />
                    <select value={it.gst_rate} onChange={e => updateItem(i, { gst_rate: Number(e.target.value) })} className="col-span-1 h-9 rounded-md border px-1 text-xs">
                      <option value="18">18</option><option value="5">5</option><option value="12">12</option><option value="28">28</option>
                    </select>
                    <button type="button" onClick={() => setItems(prev => prev.filter((_, idx) => idx !== i))} className="col-span-1 text-red-500">×</button>
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" onClick={() => setItems(prev => [...prev, { description: "", sac_code: "998299", amount: 0, gst_rate: 18 }])}>
                  + Add line item
                </Button>
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 p-3 text-sm">
              <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span>{fmt(base)}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">GST (18% avg)</span><span>{fmt(gst)}</span></div>
              <div className="flex justify-between font-semibold text-base mt-1 border-t pt-1"><span>Total</span><span>{fmt(total)}</span></div>
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Creating…" : "Create Invoice"}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function PaymentDialog({ invoice, onClose, onPaid }: { invoice: Invoice; onClose: () => void; onPaid: () => void }) {
  const [amount, setAmount] = useState(invoice.total);
  const [method, setMethod] = useState("UPI");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if ((amount || 0) <= 0) { setError("Enter a valid amount"); return; }
    setError(null); setSaving(true);
    try {
      await BillingAPI.recordPayment(invoice.id, { amount: Number(amount), payment_method: method });
      onPaid();
      onClose();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-sm">
        <CardHeader><CardTitle>Record Payment</CardTitle><CardDescription>{invoice.invoice_number} · outstanding {fmt(invoice.total)}</CardDescription></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <div><Label>Amount</Label><Input type="number" step="0.01" min="0" value={amount} onChange={e => setAmount(Number(e.target.value))} required /></div>
            <div><Label>Method</Label>
              <select value={method} onChange={e => setMethod(e.target.value)} className="w-full h-10 rounded-md border px-2 text-sm">
                <option>UPI</option><option>Bank Transfer</option><option>Cheque</option><option>Cash</option>
              </select>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Record Payment"}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
