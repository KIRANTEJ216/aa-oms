import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
export default function Page() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Client Portal</h1>
      <Card><CardHeader><CardTitle>Client Portal</CardTitle><CardDescription>Client self-service — my tasks, shared documents, invoices, filing status.</CardDescription></CardHeader><CardContent><p className="text-sm text-slate-500">Module wiring in progress. API: /api/v1/client</p></CardContent></Card>
    </div>
  );
}
