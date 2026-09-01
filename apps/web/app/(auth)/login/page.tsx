"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { loginSchema, type LoginInput } from "@/lib/validations";
import { apiFetch } from "@/lib/api-client";
import { firebaseEnabled, getFirebaseAuth } from "@/lib/firebase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

async function loginWithFirebaseIdToken(auth: any): Promise<void> {
  const { getIdToken } = await import("firebase/auth");
  const user = auth.currentUser;
  if (!user) throw new Error("Firebase signed in but no user returned");
  const idToken = await getIdToken(user);
  const res = await apiFetch("/api/v1/auth/firebase", { method: "POST", body: JSON.stringify({ id_token: idToken }) });
  localStorage.setItem("caoms_access_token", res.access_token);
  if (res.refresh_token) localStorage.setItem("caoms_refresh_token", res.refresh_token);
  window.location.href = "/";
}

export default function LoginPage() {
  const { register, handleSubmit, formState: { errors } } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [fbLoading, setFbLoading] = useState(false);
  const tenantMode = process.env.NEXT_PUBLIC_TENANT_MODE || "single";
  async function onSubmit(data: LoginInput) {
    setErr(""); setLoading(true);
    try {
      // Hybrid: if Firebase is configured, prefer Firebase sign-in; fall back to legacy JWT login
      if (firebaseEnabled) {
        try {
          const auth = getFirebaseAuth()!;
          const { signInWithEmailAndPassword } = await import("firebase/auth");
          await signInWithEmailAndPassword(auth, data.email, data.password);
          await loginWithFirebaseIdToken(auth);
          return;
        } catch (e: any) {
          // Unknown to Firebase (e.g. legacy-local users) / config error → try legacy login
          await legacyLogin(data);
          return;
        }
      }
      await legacyLogin(data);
    } catch (e: any) { setErr(e.message); } finally { setLoading(false); }
  }
  async function legacyLogin(data: LoginInput) {
    const res = await apiFetch("/api/v1/auth/login", { method: "POST", body: JSON.stringify(data) });
    if (res.mfa_required) { localStorage.setItem("caoms_temp_token", res.temp_token); window.location.href="/mfa"; return; }
    localStorage.setItem("caoms_access_token", res.access_token);
    if (res.refresh_token) localStorage.setItem("caoms_refresh_token", res.refresh_token);
    window.location.href="/";
  }
  async function onGoogle() {
    setErr(""); setFbLoading(true);
    try {
      const { signInWithPopup, GoogleAuthProvider } = await import("firebase/auth");
      const auth = getFirebaseAuth()!;
      await signInWithPopup(auth, new GoogleAuthProvider());
      await loginWithFirebaseIdToken(auth);
    } catch (e: any) { setErr(e.message); } finally { setFbLoading(false); }
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
            <Button type="submit" className="w-full" disabled={loading || fbLoading}>{loading ? "Signing in…" : "Sign in"}</Button>
            {firebaseEnabled && (
              <>
                <div className="relative my-3"><div className="absolute inset-0 flex items-center"><span className="w-full border-t border-slate-200" /></div><div className="relative flex justify-center text-xs"><span className="bg-white px-2 text-slate-400">or</span></div></div>
                <Button type="button" variant="outline" className="w-full" disabled={fbLoading || loading} onClick={onGoogle}>{fbLoading ? "Connecting to Google…" : "Continue with Google"}</Button>
              </>
            )}
            <p className="text-center text-xs text-slate-500"><a href="/register" className="underline">Create account</a> · <a href="/forgot-password" className="underline">Forgot password?</a></p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
