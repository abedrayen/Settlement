import clsx from "clsx";
import { ReactNode } from "react";

type Accent = "blue" | "emerald" | "amber" | "slate";

const accents: Record<Accent, { bg: string; icon: string }> = {
  blue: { bg: "bg-blue-50", icon: "text-blue-600" },
  emerald: { bg: "bg-emerald-50", icon: "text-emerald-600" },
  amber: { bg: "bg-amber-50", icon: "text-amber-600" },
  slate: { bg: "bg-slate-100", icon: "text-slate-600" },
};

export function KpiCard({
  label,
  value,
  sub,
  icon,
  accent = "blue",
  trend,
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  accent?: Accent;
  trend?: { value: string; positive?: boolean };
}) {
  const a = accents[accent];
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
          <p className="text-xl font-semibold text-slate-900 mt-1 tracking-tight tabular-nums">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
          {trend && (
            <p className={clsx("text-xs font-medium mt-1.5", trend.positive ? "text-emerald-600" : "text-red-600")}>
              {trend.value}
            </p>
          )}
        </div>
        {icon && (
          <div className={clsx("p-2 rounded-lg shrink-0", a.bg, a.icon)}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
