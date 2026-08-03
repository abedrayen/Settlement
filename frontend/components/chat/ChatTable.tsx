import { ReactNode } from "react";
import clsx from "clsx";

export function ChatTable({
  title,
  columns,
  rows,
  emptyMessage = "No data",
}: {
  title?: string;
  columns: { key: string; label: string; align?: "left" | "center" | "right" }[];
  rows: { key: string; cells: Record<string, ReactNode>; highlight?: boolean }[];
  emptyMessage?: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white px-4 py-6 text-center text-xs text-slate-500">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      {title && (
        <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50/80">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">{title}</p>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={clsx(
                    "px-3 py-2 font-semibold text-slate-500",
                    col.align === "right" && "text-right",
                    col.align === "center" && "text-center",
                    (!col.align || col.align === "left") && "text-left"
                  )}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <tr
                key={row.key}
                className={clsx(
                  "transition-colors",
                  row.highlight ? "bg-red-50/80" : "hover:bg-slate-50/50"
                )}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={clsx(
                      "px-3 py-2.5 text-slate-700",
                      col.align === "right" && "text-right",
                      col.align === "center" && "text-center",
                      (!col.align || col.align === "left") && "text-left"
                    )}
                  >
                    {row.cells[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
