import clsx from "clsx";
import { ReactNode } from "react";

export function Alert({
  children,
  variant = "info",
  title,
  action,
}: {
  children?: ReactNode;
  variant?: "info" | "warning" | "danger" | "success";
  title?: string;
  action?: ReactNode;
}) {
  const styles = {
    info: "bg-blue-50 border-blue-200 text-blue-800",
    warning: "bg-amber-50 border-amber-200 text-amber-900",
    danger: "bg-red-50 border-red-200 text-red-800",
    success: "bg-emerald-50 border-emerald-200 text-emerald-800",
  };
  return (
    <div className={clsx("rounded-xl border px-4 py-3 flex items-center justify-between gap-4", styles[variant])}>
      <div>
        {title && <div className="font-semibold text-sm">{title}</div>}
        {children && <div className="text-sm mt-0.5 opacity-90">{children}</div>}
      </div>
      {action}
    </div>
  );
}
