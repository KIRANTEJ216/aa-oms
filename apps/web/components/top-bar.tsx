"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { getSessionUser, signOut, type SessionUser } from "@/lib/session";

export function TopBar({ email, role }: { email?: string; role?: string }) {
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    setUser(getSessionUser());
  }, []);

  const displayEmail = user?.email || email || "info@aaravadvisors.in";
  const displayRole = user?.role || role || "Firm Admin";

  return (
    <header className="flex h-14 items-center justify-between border-b bg-white px-4">
      <div className="flex items-center gap-2 min-w-0">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
          {displayEmail.slice(0, 2).toUpperCase()}
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{displayEmail}</div>
          <span className="rounded bg-slate-900 px-2 py-0.5 text-xs text-white">{displayRole}</span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="hidden sm:inline text-xs text-slate-500">Asia/Mumbai · Firestore asia-south1</span>
        <Button variant="outline" size="sm" onClick={signOut}>Sign out</Button>
      </div>
    </header>
  );
}
