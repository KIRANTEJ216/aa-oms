"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { loginSchema, type LoginInput } from "@/lib/validations";
import { apiFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const { register, handleSubmit, formState: { errors } } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const tenantMode = process.env.NEXT_PUBLIC_TENANT_MODE || "single";
  async function onSubmit(data: LoginInput) {
    setErr(""); setLoading(true);
    try {
      const res = await apiFetch("/api/v1/auth/login", { method: "POST", body: JSON.stringify(data) });
      if (res.mfa_required) { localStorage.setItem("caoms_temp_token", res.temp_token); window.location.href="/mfa"; return; }
      localStorage.setItem("caoms_access_token", res.access_token);
      window.location.href="/";
    } catch (e: any) { setErr(e.message); } finally { setLoading(false); }
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader><CardTitle>Sign in to CAOMS</CardTitle><CardDescription>Aarav Advisors — TENANT_MODE={tenantMode}</CardDescription></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" placeholder="info@aaravadvisors.in" {...register("email")} />{errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}</div>
            <div className="space-y-2"><Label htmlFor="password">Password</Label><Input id="password" type="password" {...register("password")} />{errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}</div>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <Button type="submit" className="w-full" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</Button>
            <p className="text-center text-xs text-slate-500"><a href="/register" className="underline">Create account</a> · <a href="/forgot-password" className="underline">Forgot password?</a></p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
