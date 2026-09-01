"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { registerSchema } from "@/lib/validations";
import { z } from "zod";
import { apiFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
type Form = z.infer<typeof registerSchema>;
export default function RegisterPage() {
  const { register, handleSubmit, formState: { errors } } = useForm<Form>({ resolver: zodResolver(registerSchema) });
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  async function onSubmit(data: Form) {
    setErr(""); setMsg("");
    try { await apiFetch("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) }); setMsg("Account created. Please sign in."); }
    catch (e: any) { setErr(e.message); }
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader><CardTitle>Create account</CardTitle><CardDescription>Firm pilot — request access</CardDescription></CardHeader>
        <CardContent><form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
          <div><Label>Name</Label><Input {...register("name")} />{errors.name && <p className="text-xs text-red-600">{errors.name.message}</p>}</div>
          <div><Label>Email</Label><Input {...register("email")} />{errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}</div>
          <div><Label>Mobile</Label><Input {...register("mobile")} />{errors.mobile && <p className="text-xs text-red-600">{errors.mobile.message}</p>}</div>
          <div><Label>Password (min 8)</Label><Input type="password" {...register("password")} />{errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}</div>
          {err && <p className="text-sm text-red-600">{err}</p>}{msg && <p className="text-sm text-green-600">{msg}</p>}
          <Button type="submit" className="w-full">Create account</Button>
          <p className="text-center text-xs text-slate-500"><a href="/login" className="underline">Back to login</a></p>
        </form></CardContent>
      </Card>
    </div>
  );
}
