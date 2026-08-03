"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet, apiPatch } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/LoadingState";
import { LoadingState } from "@/components/ui/LoadingState";
import { formatCurrency, formatPercent } from "@/lib/format";

type Task = {
  task_id: string;
  task_type: string;
  customer_code: number | null;
  legal_name?: string | null;
  display_name?: string | null;
  settlement_code: number | null;
  status: string;
  assigned_queue: string;
  reason: string;
  risk_tier?: string | null;
  decision_payload?: Record<string, unknown> | null;
  resolution_note?: string | null;
  resolved_by?: string | null;
  created_at: string;
};

const APPROVER_ROLES = new Set(["manager", "compliance", "admin"]);

export default function WorkflowsPage() {
  const { role } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"open" | "pending_approval" | "all">("all");
  const [note, setNote] = useState<Record<string, string>>({});
  const canApprove = APPROVER_ROLES.has(role);

  const load = () =>
    apiGet<Task[]>("/api/workflows")
      .then(setTasks)
      .catch(console.error)
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    if (filter === "all") return tasks;
    if (filter === "open") return tasks.filter((t) => t.status === "open" || t.status === "pending_approval");
    return tasks.filter((t) => t.status === filter);
  }, [tasks, filter]);

  const update = async (id: string, status: string) => {
    await apiPatch(`/api/workflows/${id}`, { status, resolution_note: note[id] || undefined });
    setNote((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    load();
  };

  if (loading) return <LoadingState message="Loading workflow inbox..." />;

  const openCount = tasks.filter((t) => t.status === "open" || t.status === "pending_approval").length;

  return (
    <div className="page-container">
      <PageHeader
        title="Workflow Inbox"
        badge={
          openCount > 0 ? (
            <Badge variant="warning">{openCount} open</Badge>
          ) : (
            <Badge variant="success">Clear</Badge>
          )
        }
      />

      <div className="flex gap-2 mb-4">
        {(
          [
            ["all", "All"],
            ["open", "Open / Pending"],
            ["pending_approval", "Pending approval"],
          ] as const
        ).map(([key, label]) => (
          <Button
            key={key}
            size="sm"
            variant={filter === key ? "primary" : "outline"}
            onClick={() => setFilter(key)}
          >
            {label}
          </Button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="No escalation tasks"
          action={
            <Button variant="outline" size="sm" onClick={() => (window.location.href = "/chat")}>
              Open agent
            </Button>
          }
        />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50/80 text-slate-500 text-xs uppercase tracking-wide">
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Borrower</th>
                <th className="px-4 py-3 text-left">Recommendation</th>
                <th className="px-4 py-3 text-left">Risk</th>
                <th className="px-4 py-3 text-left">Queue</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((t) => {
                const payload = t.decision_payload || {};
                const display =
                  t.display_name ||
                  (t.legal_name && t.customer_code
                    ? `${t.legal_name} (${t.customer_code})`
                    : t.customer_code
                      ? String(t.customer_code)
                      : "—");
                const rr = payload.recovery_rate as number | undefined;
                const ev = payload.expected_value as number | undefined;
                const inst = payload.installments as number | undefined;
                return (
                  <tr key={t.task_id} className="hover:bg-slate-50/50 transition-colors align-top">
                    <td className="px-4 py-3 font-medium">{t.task_type}</td>
                    <td className="px-4 py-3">
                      {t.customer_code ? (
                        <Link href={`/borrowers/${t.customer_code}`} className="text-brand-600 underline">
                          {display}
                        </Link>
                      ) : (
                        display
                      )}
                      <div className="text-xs text-slate-500 mt-0.5">{t.reason}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {rr != null ? (
                        <div className="text-xs space-y-0.5">
                          <div>{formatPercent(rr)} · {inst ?? "—"} installments</div>
                          {ev != null && <div>EV {formatCurrency(ev)}</div>}
                          {payload.solver_status != null && (
                            <div className="text-slate-400">Solver: {String(payload.solver_status)}</div>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {t.risk_tier ? (
                        <Badge variant={t.risk_tier === "high" ? "danger" : t.risk_tier === "medium" ? "warning" : "info"}>
                          {t.risk_tier}
                        </Badge>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{t.assigned_queue}</td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={
                          t.status === "open" || t.status === "pending_approval"
                            ? "warning"
                            : t.status === "approved" || t.status === "resolved"
                              ? "success"
                              : "info"
                        }
                      >
                        {t.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 space-y-2 min-w-[200px]">
                      {(t.status === "open" || t.status === "pending_approval") && (
                        <>
                          <input
                            className="w-full text-xs border border-slate-200 rounded px-2 py-1"
                            placeholder="Resolution note"
                            value={note[t.task_id] || ""}
                            onChange={(e) => setNote((prev) => ({ ...prev, [t.task_id]: e.target.value }))}
                          />
                          <div className="flex flex-wrap gap-1">
                            {canApprove && t.status === "pending_approval" && (
                              <>
                                <Button variant="ghost" size="sm" onClick={() => update(t.task_id, "approved")}>
                                  Approve
                                </Button>
                                <Button variant="outline" size="sm" onClick={() => update(t.task_id, "rejected")}>
                                  Reject
                                </Button>
                                <Button variant="outline" size="sm" onClick={() => update(t.task_id, "escalated")}>
                                  Escalate
                                </Button>
                              </>
                            )}
                            <Button variant="ghost" size="sm" onClick={() => update(t.task_id, "acknowledged")}>
                              Acknowledge
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => update(t.task_id, "resolved")}>
                              Resolve
                            </Button>
                          </div>
                        </>
                      )}
                      {t.resolved_by && (
                        <div className="text-[10px] text-slate-400">
                          by {t.resolved_by}
                          {t.resolution_note ? ` — ${t.resolution_note}` : ""}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
