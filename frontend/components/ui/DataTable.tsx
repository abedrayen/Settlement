import { ReactNode } from "react";

export function DataTable({
  columns,
  rows,
  emptyMessage = "No data available",
}: {
  columns: { key: string; label: string; align?: "left" | "center" | "right" }[];
  rows: { key: string; cells: Record<string, ReactNode> }[];
  emptyMessage?: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="card p-8 text-center text-sm text-slate-500">{emptyMessage}</div>
    );
  }
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-200">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 font-semibold text-slate-600 text-${col.align || "left"}`}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <tr key={row.key} className="hover:bg-slate-50/50 transition-colors">
                {columns.map((col) => (
                  <td key={col.key} className={`px-4 py-3 text-slate-700 text-${col.align || "left"}`}>
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
