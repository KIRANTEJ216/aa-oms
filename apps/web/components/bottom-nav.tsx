"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { filterNav } from "@/components/sidebar";

export function BottomNav({ role = "Firm Admin" }: { role?: string }) {
  const pathname = usePathname();
  const visible = filterNav(role).slice(0, 6);
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t bg-white md:hidden">
      <div className="flex items-stretch justify-around">
        {visible.map(i => {
          const active = pathname === i.href || (i.href !== "/" && pathname.startsWith(i.href));
          const Icon = i.icon;
          return (
            <Link key={i.href} href={i.href} className={`flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] ${active ? "text-slate-900 font-semibold" : "text-slate-500"}`}>
              <Icon className="h-5 w-5" />
              {i.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
