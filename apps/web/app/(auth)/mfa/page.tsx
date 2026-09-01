"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { mfaSchema } from "@/lib/validations";
import { z } from "zod";
import { apiFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
type Form = z.infer<typeof mfaSchema>;
export default function MfaPage() {
  const { register, handleSubmit } = useForm<Form>({ resolver: zodResolver(mfaSchema) });
  const [err, setErr] = useState("");
  async function onSubmit(data: Form) {
    setErr("");
    try {
      const temp = localStorage.getItem("caoms_temp_token");
      const res = await apiFetch("/api/v1/auth/mfa/verify", { method: "POST", body: JSON.stringify({ temp_token: temp, code: data.code }) });
      localStorage.setItem("caoms_access_token", res.access_token); localStorage.removeItem("caoms_temp_token"); window.location.href="/";
    } catch (e: any) { setErr(e.message); }
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader><CardTitle>Two-factor verification</CardTitle><CardDescription>Enter the 6-digit code from your authenticator</CardDescription></CardHeader>
        <CardContent><form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div><Label>Code</Label><Input placeholder="123456" maxLength={6} {...register("code")} /></div>
          {err && <p className="text-sm text-red-600">{err}</p>}
          <Button type="submit" className="w-full">Verify</Button>
        </form></CardContent>
      </Card>
    </div>
  );
}
