"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useAuth, ROLE_LABELS } from "@/components/AuthProvider";
import { canSeeNav } from "@/lib/roles";
import {
  IconAudit,
  IconChart,
  IconChat,
  IconDoc,
  IconDashboard,
  IconSettings,
  IconShield,
  IconSparkle,
  IconUser,
  IconWorkflow,
} from "@/components/icons";

const PRIMARY_NAV: { href: string; label: string; key: string; icon: typeof IconChat }[] = [
  { href: "/workspace", label: "Collection Workspace", key: "workspace", icon: IconUser },
  { href: "/optimization", label: "Settlement Optimization", key: "optimization", icon: IconSparkle },
  { href: "/portfolio", label: "Portfolio Monitoring", key: "portfolio", icon: IconChart },
  { href: "/approvals", label: "Approvals & Exceptions", key: "approvals", icon: IconWorkflow },
  { href: "/executive", label: "Executive Dashboard", key: "executive", icon: IconDashboard },
  { href: "/assistant", label: "AI Assistant", key: "assistant", icon: IconChat },
];

const SECONDARY_NAV: { href: string; label: string; key: string; icon: typeof IconChat }[] = [
  { href: "/documents", label: "Documents", key: "documents", icon: IconDoc },
  { href: "/monitoring", label: "Model Health", key: "monitoring", icon: IconShield },
  { href: "/audit", label: "Audit", key: "audit", icon: IconAudit },
  { href: "/settings", label: "Settings", key: "settings", icon: IconSettings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { role, user, logout } = useAuth();

  const isActive = (href: string) =>
    pathname === href || (href !== "/assistant" && pathname.startsWith(href + "/"));

  const initials = (user?.full_name || user?.email || role)
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const renderItems = (items: typeof PRIMARY_NAV) =>
    items
      .filter((item) => canSeeNav(role, item.key))
      .map((item) => {
        const Icon = item.icon;
        const active = isActive(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={clsx(
              "flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium transition-colors",
              active ? "nav-item-active" : "nav-item-inactive",
            )}
          >
            <Icon className={clsx("w-4 h-4 shrink-0", active ? "text-white" : "text-slate-500")} />
            <span className="leading-snug">{item.label}</span>
          </Link>
        );
      });

  return (
    <aside className="w-[240px] min-h-screen bg-sidebar text-slate-300 flex flex-col shrink-0 border-r border-sidebar-border">
      <div className="px-4 py-4 border-b border-sidebar-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <IconSparkle className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white tracking-tight">Settlement AI</h1>
            <p className="text-[10px] text-slate-500">Portfolio Intelligence</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-2.5 space-y-0.5 overflow-y-auto">
        {renderItems(PRIMARY_NAV)}
        <div className="my-3 border-t border-sidebar-border" />
        <p className="px-2.5 pb-1 text-[10px] uppercase tracking-wide text-slate-600">Secondary</p>
        {renderItems(SECONDARY_NAV)}
      </nav>

      <div className="p-3 border-t border-sidebar-border space-y-2.5">
        <div className="flex items-center gap-2.5 px-1">
          <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-[11px] font-semibold text-white">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-white truncate">{user?.full_name || ROLE_LABELS[role]}</p>
            <p className="text-[10px] text-slate-500 truncate">{ROLE_LABELS[role]}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={logout}
          className="w-full text-left text-[11px] text-slate-500 hover:text-slate-200 px-1 py-1"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
