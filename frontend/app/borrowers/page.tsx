"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { useRole } from "@/components/AuthProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { LoadingState } from "@/components/ui/LoadingState";
import { AskAgentBridge } from "@/components/ui/DownloadableTable";
import { Badge } from "@/components/ui/Badge";

type BorrowerRow = {
  customer_code: number;
  legal_name?: string;
  segment?: string;
  settlement_status?: string;
  total_balance?: number | null;
  expected_value?: number | null;
  optimal_rr?: number | null;
  p_fulfillment?: number | null;
};

export default function BorrowersIndexPage() {
  const [rows, setRows] = useState<BorrowerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [segment, setSegment] = useState("");
  const [status, setStatus] = useState("");
  const router = useRouter();
  const { role } = useRole();

  useEffect(() => {
    setLoading(true);
    apiGet<BorrowerRow[]>("/api/borrowers", role)
      .then((data) => {
        setRows(data);
        setError(null);
      })
      .catch(() => setError("Unable to load borrower directory."))
      .finally(() => setLoading(false));
  }, [role]);

  const segments = useMemo(
    () => Array.from(new Set(rows.map((r) => r.segment).filter(Boolean) as string[])).sort(),
    [rows],
  );
  const statuses = useMemo(
    () => Array.from(new Set(rows.map((r) => r.settlement_status).filter(Boolean) as string[])).sort(),
    [rows],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (segment && r.segment !== segment) return false;
      if (status && r.settlement_status !== status) return false;
      if (!q) return true;
      return (
        String(r.customer_code).includes(q) ||
        (r.legal_name || "").toLowerCase().includes(q)
      );
    });
  }, [rows, query, segment, status]);

  if (loading) return <LoadingState message="Loading borrower directory…" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Borrowers"
        actions={<AskAgentBridge question="Show me the top recommended settlement offers in the portfolio." />}
      />

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-md px-3 py-2">{error}</p>
      )}

      <div className="card p-4">
        <div className="grid md:grid-cols-3 gap-3">
          <label className="space-y-1">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Search</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name or customer code"
              className="input-field w-full"
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Segment</span>
            <select value={segment} onChange={(e) => setSegment(e.target.value)} className="input-field w-full">
              <option value="">All segments</option>
              {segments.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Status</span>
            <select value={status} onChange={(e) => setStatus(e.target.value)} className="input-field w-full">
              <option value="">All statuses</option>
              {statuses.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3 font-medium">Customer</th>
                <th className="px-4 py-3 font-medium">Code</th>
                <th className="px-4 py-3 font-medium">Segment</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Balance</th>
                <th className="px-4 py-3 font-medium text-right">EV</th>
                <th className="px-4 py-3 font-medium text-right">Opt. RR</th>
                <th className="px-4 py-3 font-medium text-right">P(Fulfil)</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                    No borrowers match the current filters.
                  </td>
                </tr>
              ) : (
                filtered.map((r) => (
                  <tr
                    key={r.customer_code}
                    onClick={() => router.push(`/borrowers/${r.customer_code}`)}
                    className="border-b border-slate-100 hover:bg-blue-50/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 font-medium text-slate-900">{r.legal_name || "—"}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-600">{r.customer_code}</td>
                    <td className="px-4 py-2.5">
                      {r.segment ? <Badge>{r.segment}</Badge> : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">{r.settlement_status || "—"}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-slate-700">
                      {r.total_balance != null ? `£${Number(r.total_balance).toLocaleString()}` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-slate-700">
                      {r.expected_value != null ? `£${Number(r.expected_value).toLocaleString()}` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-slate-700">
                      {r.optimal_rr != null ? `${(Number(r.optimal_rr) * 100).toFixed(0)}%` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-slate-700">
                      {r.p_fulfillment != null ? `${(Number(r.p_fulfillment) * 100).toFixed(0)}%` : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
