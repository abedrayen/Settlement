import clsx from "clsx";
import { ReactNode } from "react";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";

const variants: Record<BadgeVariant, string> = {
  default: "bg-slate-100 text-slate-700",
  success: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200/60",
  warning: "bg-amber-50 text-amber-700 ring-1 ring-amber-200/60",
  danger: "bg-red-50 text-red-700 ring-1 ring-red-200/60",
  info: "bg-blue-50 text-blue-700 ring-1 ring-blue-200/60",
};

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) {
  return (
    <span className={clsx("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium", variants[variant], className)}>
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, BadgeVariant> = {
    passed: "success",
    ok: "success",
    open: "warning",
    blocked: "danger",
    alert: "danger",
    warning: "warning",
    acknowledged: "info",
    resolved: "success",
  };
  return <Badge variant={map[status.toLowerCase()] || "default"}>{status}</Badge>;
}
