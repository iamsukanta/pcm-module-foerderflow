"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  ArrowLeftRight,
  Inbox,
  Users,
  Banknote,
  Zap,
  Landmark,
  FolderKanban,
  SplitSquareHorizontal,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Clock,
  UserCircle,
  ShieldCheck,
  Calculator,
  Table2,
  Wallet,
  LayoutGrid,
  CalendarOff,
  Gift,
  Coins,
  ScrollText,
  TrendingUp,
  FlaskConical,
  PieChart,
  FileText,
  FileInput,
  SlidersHorizontal,
} from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  badgeKey?: "kritischeFristen";
};

const TAGLICH: NavItem[] = [
  { href: "/dashboard", label: "Übersicht", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/transaktionen", label: "Transaktionen", icon: ArrowLeftRight },
  { href: "/dashboard/review", label: "Review-Inbox", icon: Inbox },
  {
    href: "/dashboard/fristen",
    label: "Fristen",
    icon: Clock,
    badgeKey: "kritischeFristen",
  },
];

const MONATLICH: NavItem[] = [
  { href: "/dashboard/pcm/abrechnung", label: "PCM-Abrechnung", icon: Calculator },
  { href: "/dashboard/pcm/lohnimport", label: "Lohnimport", icon: FileInput },
  { href: "/dashboard/pcm/prognose", label: "Personalkostenprognose", icon: TrendingUp },
  { href: "/dashboard/pcm/szenarien", label: "Szenario-Planer", icon: FlaskConical },
  { href: "/dashboard/mittelabrufe", label: "Mittelabrufe", icon: Banknote },
  { href: "/dashboard/buchungsregeln", label: "Buchungsregeln", icon: Zap },
];

// PERSONNEL group (Sidebar Integration Guide §3) — people-centric screens.
// Only routes with a built page are listed; further items (Leave, Bonus
// Templates, Payroll Allocations, VWN, Audit Trail) are added as they land.
const PERSONAL: NavItem[] = [
  { href: "/dashboard/personal", label: "Mitarbeitende", icon: Users },
  { href: "/dashboard/personal/gehaltserfassung", label: "Gehaltserfassung", icon: Wallet },
  { href: "/dashboard/pcm/stellenplan", label: "Stellenplan", icon: LayoutGrid },
  { href: "/dashboard/pcm/abwesenheiten", label: "Abwesenheiten", icon: CalendarOff },
  { href: "/dashboard/pcm/bonusvorlagen", label: "Bonusvorlagen", icon: Gift },
  { href: "/dashboard/pcm/zulagen", label: "Zulagen & Boni", icon: Coins },
  { href: "/dashboard/pcm/zuordnungen", label: "Lohnkostenzuordnungen", icon: PieChart },
  { href: "/dashboard/pcm/vwn", label: "VWN-Bericht", icon: FileText },
  { href: "/dashboard/pcm/protokoll", label: "Protokoll", icon: ScrollText },
];

const VERWALTUNG: NavItem[] = [
  { href: "/dashboard/foerdermassnahmen", label: "Fördermassnahmen", icon: Landmark },
  { href: "/dashboard/kostenstellen", label: "Kostenstellen", icon: FolderKanban },
  { href: "/dashboard/konten", label: "Bank- & Kassenkonten", icon: Banknote },
  {
    href: "/dashboard/verteilungsschluessel",
    label: "Verteilungsschlüssel",
    icon: SplitSquareHorizontal,
  },
  { href: "/dashboard/umlage-source-scopes", label: "Umlage-Pools", icon: SplitSquareHorizontal },
  { href: "/dashboard/haushaltsjahre", label: "Haushaltsjahre", icon: CalendarDays },
  { href: "/dashboard/pcm/tarife", label: "Tarif-Register", icon: Table2 },
  { href: "/dashboard/pcm/einstellungen", label: "PCM-Einstellungen", icon: SlidersHorizontal },
];

function NavLink({
  href,
  label,
  icon: Icon,
  exact = false,
  badgeCount,
}: NavItem & { badgeCount?: number }) {
  const pathname = usePathname();
  const isActive = exact
    ? pathname === href
    : pathname === href || pathname.startsWith(href + "/");

  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 px-3 py-2 my-0.5 rounded-soft text-sm cursor-pointer transition-all ${
        isActive
          ? "bg-soft-surface text-soft-ink font-medium shadow-soft border border-soft-line"
          : "text-soft-ink2 hover:bg-soft-ink/5"
      }`}
    >
      <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-soft-accent" : "text-soft-ink3"}`} />
      <span className="flex-1 truncate">{label}</span>
      {badgeCount !== undefined && badgeCount > 0 && (
        <span
          aria-label={`${badgeCount} kritische Einträge`}
          className="numeric text-[10px] font-semibold px-1.5 py-0.5 rounded-soft-xs bg-soft-critSoft text-soft-crit min-w-[1.25rem] text-center"
        >
          {badgeCount}
        </span>
      )}
    </Link>
  );
}

type SidebarNavProps = {
  kritischeFristen?: number;
  /** Aus Session: zeigt den "VoluLink Super-Admin"-Link nur, wenn true. */
  isSuperAdmin?: boolean;
};

export function SidebarNav({ kritischeFristen = 0, isSuperAdmin = false }: SidebarNavProps) {
  const pathname = usePathname();
  const hasVerwaltungActive = VERWALTUNG.some(
    (item) => pathname === item.href || pathname.startsWith(item.href + "/"),
  );
  const [verwaltungOpen, setVerwaltungOpen] = useState(hasVerwaltungActive);

  function badgeFor(item: NavItem): number | undefined {
    if (item.badgeKey === "kritischeFristen") return kritischeFristen;
    return undefined;
  }

  return (
    <nav className="flex-1 px-3 py-4 flex flex-col">
      {/* TÄGLICH */}
      <p className="text-[10px] uppercase tracking-widest text-soft-ink3 font-semibold px-3 mb-1">
        Täglich
      </p>
      <div className="space-y-0.5">
        {TAGLICH.map((item) => (
          <NavLink key={item.href} {...item} badgeCount={badgeFor(item)} />
        ))}
      </div>

      {/* MONATLICH */}
      <p className="text-[10px] uppercase tracking-widest text-soft-ink3 font-semibold px-3 mb-1 mt-4">
        Monatlich
      </p>
      <div className="space-y-0.5">
        {MONATLICH.map((item) => (
          <NavLink key={item.href} {...item} badgeCount={badgeFor(item)} />
        ))}
      </div>

      {/* PERSONAL */}
      <p className="text-[10px] uppercase tracking-widest text-soft-ink3 font-semibold px-3 mb-1 mt-4">
        Personal
      </p>
      <div className="space-y-0.5">
        {PERSONAL.map((item) => (
          <NavLink key={item.href} {...item} badgeCount={badgeFor(item)} />
        ))}
      </div>

      {/* VERWALTUNG */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setVerwaltungOpen((o) => !o)}
          className="w-full flex items-center justify-between px-3 mb-1"
        >
          <span className="text-[10px] uppercase tracking-widest text-soft-ink3 font-semibold">
            Verwaltung
          </span>
          {verwaltungOpen ? (
            <ChevronDown className="h-3 w-3 text-soft-ink3" />
          ) : (
            <ChevronRight className="h-3 w-3 text-soft-ink3" />
          )}
        </button>
        {verwaltungOpen && (
          <div className="space-y-0.5">
            {VERWALTUNG.map((item) => (
              <NavLink key={item.href} {...item} badgeCount={badgeFor(item)} />
            ))}
          </div>
        )}
      </div>

      {/* Persönlich / Plattform */}
      <div className="mt-auto pt-4 border-t border-soft-line2">
        <NavLink href="/dashboard/profil" label="Mein Profil" icon={UserCircle} />
        {isSuperAdmin && (
          <NavLink href="/admin" label="VoluLink Super-Admin" icon={ShieldCheck} />
        )}
      </div>
    </nav>
  );
}
