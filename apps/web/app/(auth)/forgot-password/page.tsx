"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
export default function ForgotPage() {
  const [email, setEmail] = useState(""); const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  async function submit(e: React.FormEvent) { e.preventDefault(); setErr(""); setMsg(""); try { await apiFetch("/api/v1/auth/forgot-password", { method:"POST", body: JSON.stringify({ email })}); setMsg("If the account exists, a reset link has been sent (15 min expiry)."); } catch(e:any){ setErr(e.message);} }
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-sm"><CardHeader><CardTitle>Forgot password</CardTitle></CardHeader><CardContent><form onSubmit={submit} className="space-y-4"><div><Label>Email</Label><Input value={email} onChange={e=>setEmail(e.target.value)} placeholder="info@aaravadvisors.in" /></div>{err&&<p className="text-sm text-red-600">{err}</p>}{msg&&<p className="text-sm text-green-600">{msg}</p>}<Button type="submit" className="w-full">Send reset link</Button><p className="text-center text-xs text-slate-500"><a href="/login" className="underline">Back to login</a></p></form></CardContent></Card>
    </div>
  );
}
