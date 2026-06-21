"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LogOut,
  ShieldCheck,
  Building2,
  UsersRound,
  ArrowLeft,
  LayoutDashboard,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
};

const ITEMS: NavItem[] = [
  { href: "/admin", label: "Übersicht", icon: LayoutDashboard, exact: true },
  { href: "/admin/organisations", label: "Organisationen", icon: Building2 },
  { href: "/admin/users", label: "User", icon: UsersRound },
];

type Props = {
  displayName: string;
  email: string | null | undefined;
};

export function AdminSidebar({ displayName, email }: Props) {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-soft-ink/95 text-white flex-shrink-0 flex flex-col">
      <div className="p-5 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-soft-xs bg-soft-accent flex items-center justify-center text-white shadow-soft">
            <ShieldCheck className="h-4 w-4" aria-hidden />
          </div>
          <div>
            <div className="text-[15px] font-semibold -tracking-[0.01em]">VoluLink Admin</div>
            <div className="text-[10.5px] text-white/60 -mt-0.5">Plattform-Verwaltung</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 flex flex-col">
        <p className="text-[10px] uppercase tracking-widest text-white/50 font-semibold px-3 mb-1">
          Plattform
        </p>
        <div className="space-y-0.5">
          {ITEMS.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 my-0.5 rounded-soft text-sm transition-all ${
                  active
                    ? "bg-white/15 text-white font-medium"
                    : "text-white/70 hover:text-white hover:bg-white/10"
                }`}
              >
                <Icon
                  className={`h-4 w-4 shrink-0 ${active ? "text-soft-accent" : "text-white/60"}`}
                  aria-hidden
                />
                <span className="flex-1 truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>

        <div className="mt-auto pt-4 border-t border-white/15">
          <Link
            href="/dashboard"
            className="flex items-center gap-2.5 px-3 py-2 my-0.5 rounded-soft text-sm text-white/70 hover:text-white hover:bg-white/10 transition-all"
          >
            <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden />
            <span>Zum Kunden-Dashboard</span>
          </Link>
        </div>
      </nav>

      <div className="px-4 py-4 border-t border-white/15">
        <p className="text-xs text-white/80 truncate mb-0.5">{displayName}</p>
        {email && <p className="text-[10px] text-white/50 truncate mb-2">{email}</p>}
        <a
          href="/api/auth/signout"
          className="flex items-center gap-2 text-xs text-white/60 hover:text-white transition-colors"
        >
          <LogOut className="h-3.5 w-3.5" aria-hidden />
          Abmelden
        </a>
      </div>
    </aside>
  );
}
