"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { TopBar } from "@/components/top-bar";
import { BottomNav } from "@/components/bottom-nav";
import { getSessionUser } from "@/lib/session";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    setRole(getSessionUser()?.role || "Client");
  }, []);

  if (role === null) {
    return <div className="min-h-screen bg-slate-50" />;
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar role={role} />
      <div className="flex flex-1 flex-col pb-16 md:pb-0">
        <TopBar role={role} />
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
      <BottomNav role={role} />
    </div>
  );
}
