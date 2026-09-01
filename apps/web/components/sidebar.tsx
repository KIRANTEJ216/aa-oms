"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, ClipboardList, CalendarCheck, Files, Receipt, KeyRound, ShieldCheck, Building2, BarChart3, Briefcase } from "lucide-react";

export const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["all"] },
  { href: "/clients", label: "Clients", icon: Users, roles: ["all"] },
  { href: "/tasks", label: "Tasks", icon: ClipboardList, roles: ["all"] },
  { href: "/compliance", label: "Compliance", icon: CalendarCheck, roles: ["all"] },
  { href: "/documents", label: "Documents", icon: Files, roles: ["all"] },
  { href: "/billing", label: "Billing", icon: Receipt, roles: ["Firm Admin", "Partner", "Manager"] },
  { href: "/credentials", label: "Vault", icon: KeyRound, roles: ["Firm Admin", "Partner", "Manager"] },
  { href: "/reports", label: "Reports", icon: BarChart3, roles: ["Firm Admin", "Partner"] },
  { href: "/bd", label: "Business Dev", icon: Briefcase, roles: ["Firm Admin", "Partner"] },
  { href: "/audit", label: "Audit", icon: ShieldCheck, roles: ["Firm Admin", "Partner"] },
];

export function filterNav(role: string) {
  return navItems.filter(i => i.roles.includes("all") || i.roles.includes(role));
}

export function Sidebar({ role = "Firm Admin" }: { role?: string }) {
  const pathname = usePathname();
  const visible = filterNav(role);
  return (
    <aside className="hidden md:flex w-64 shrink-0 flex-col border-r bg-white">
      <div className="flex h-14 items-center gap-2 border-b px-4 font-semibold"><Building2 className="h-5 w-5" /> CAOMS <span className="ml-auto text-xs font-normal text-slate-500">aarav-advisors</span></div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {visible.map(i => {
          const active = pathname === i.href || (i.href !== "/" && pathname.startsWith(i.href));
          const Icon = i.icon;
          return (
            <Link key={i.href} href={i.href} className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm transition ${active ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`}>
              <Icon className="h-4 w-4" /> {i.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-3 text-xs text-slate-500">{role}<br/>Aarav Advisors</div>
    </aside>
  );
}
