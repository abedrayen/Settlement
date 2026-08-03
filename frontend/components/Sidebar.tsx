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
  IconSettings,
  IconShield,
  IconSparkle,
  IconUser,
  IconWorkflow,
} from "@/components/icons";

const NAV_ITEMS: { href: string; label: string; key: string; icon: typeof IconChat }[] = [
  { href: "/chat", label: "Agent", key: "chat", icon: IconChat },
  { href: "/portfolio", label: "Portfolio", key: "portfolio", icon: IconChart },
  { href: "/borrowers", label: "Borrowers", key: "borrower", icon: IconUser },
  { href: "/strategy", label: "Strategy", key: "strategy", icon: IconSparkle },
  { href: "/workflows", label: "Workflows", key: "workflows", icon: IconWorkflow },
  { href: "/documents", label: "Documents", key: "documents", icon: IconDoc },
  { href: "/monitoring", label: "Monitoring", key: "monitoring", icon: IconShield },
  { href: "/audit", label: "Audit", key: "audit", icon: IconAudit },
  { href: "/settings", label: "Settings", key: "settings", icon: IconSettings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { role, user, logout } = useAuth();

  const isActive = (href: string) =>
    pathname === href || (href !== "/chat" && pathname.startsWith(href + "/"));

  const initials = (user?.full_name || user?.email || role)
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <aside className="w-[220px] min-h-screen bg-sidebar text-slate-300 flex flex-col shrink-0 border-r border-sidebar-border">
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

      <nav className="flex-1 p-2.5 space-y-0.5">
        {NAV_ITEMS.filter((item) => canSeeNav(role, item.key)).map((item) => {
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
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-sidebar-border space-y-2.5">
        <div className="flex items-center gap-2 px-1">
          <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-[10px] font-semibold text-white uppercase">
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
          className="w-full text-left text-xs px-2.5 py-1.5 rounded-md text-slate-400 hover:text-white hover:bg-sidebar-hover transition-colors"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
