"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet, apiPatch } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { canAccess } from "@/lib/roles";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, LoadingState } from "@/components/ui/LoadingState";
import { KpiCard } from "@/components/ui/KpiCard";
import { Card } from "@/components/ui/Card";
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

type WorkflowKpis = {
  total: number;
  pending_approval: number;
  escalated: number;
  approved: number;
  rejected: number;
  approval_rate: number;
  avg_resolution_hours: number;
  sla_breaches: number;
  sla_hours: number;
};

type Tab = "pending" | "escalated" | "resolved";

export default function ApprovalsPage() {
  const { role } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [kpis, setKpis] = useState<WorkflowKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("pending");
  const [note, setNote] = useState<Record<string, string>>({});
  const canApprove = canAccess(role, "workflows_approve");

  const load = () =>
    Promise.all([
      apiGet<Task[]>("/api/workflows"),
      apiGet<WorkflowKpis>("/api/workflows/kpis"),
    ])
      .then(([t, k]) => {
        setTasks(t);
        setKpis(k);
      })
      .catch(console.error)
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    if (tab === "pending") {
      return tasks.filter((t) => t.status === "pending_approval" || t.status === "open");
    }
    if (tab === "escalated") {
      return tasks.filter((t) => t.status === "escalated");
    }
    return tasks.filter((t) =>
      ["approved", "rejected", "resolved", "acknowledged"].includes(t.status),
    );
  }, [tasks, tab]);

  const update = async (id: string, status: string) => {
    await apiPatch(`/api/workflows/${id}`, { status, resolution_note: note[id] || undefined });
    setNote((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    load();
  };

  if (loading) return <LoadingState message="Loading approvals inbox..." />;

  return (
    <div className="page-container space-y-6">
      <PageHeader
        title="Approvals & Exceptions"
        description="Review AI recommendations, policy validation, and SLA."
        badge={
          kpis && kpis.pending_approval > 0 ? (
            <Badge variant="warning">{kpis.pending_approval} pending</Badge>
          ) : (
            <Badge variant="success">Clear</Badge>
          )
        }
      />

      {kpis && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KpiCard label="Approval rate" value={`${(kpis.approval_rate * 100).toFixed(0)}%`} accent="emerald" />
          <KpiCard label="Escalated" value={String(kpis.escalated)} accent="amber" />
          <KpiCard
            label="Avg resolution"
            value={`${kpis.avg_resolution_hours.toFixed(1)}h`}
            accent="blue"
          />
          <KpiCard
            label="SLA breaches"
            value={String(kpis.sla_breaches)}
            sub={`>${kpis.sla_hours}h open`}
            accent="slate"
          />
        </div>
      )}

      <div className="flex gap-2">
        {(
          [
            ["pending", "Pending"],
            ["escalated", "Escalated"],
            ["resolved", "Resolved"],
          ] as const
        ).map(([key, label]) => (
          <Button key={key} size="sm" variant={tab === key ? "primary" : "outline"} onClick={() => setTab(key)}>
            {label}
          </Button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="No tasks in this queue"
          action={
            <Button variant="outline" size="sm" onClick={() => (window.location.href = "/assistant")}>
              Open AI Assistant
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
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
            const policyReason =
              (payload.approval_reason as string) ||
              (payload.guardrail_reason as string) ||
              t.reason;

            return (
              <Card key={t.task_id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-slate-900">{t.task_type}</span>
                      <Badge
                        variant={
                          t.status === "pending_approval" || t.status === "open"
                            ? "warning"
                            : t.status === "approved" || t.status === "resolved"
                              ? "success"
                              : t.status === "escalated"
                                ? "danger"
                                : "info"
                        }
                      >
                        {t.status}
                      </Badge>
                      {t.risk_tier && (
                        <Badge
                          variant={
                            t.risk_tier === "high" ? "danger" : t.risk_tier === "medium" ? "warning" : "info"
                          }
                        >
                          {t.risk_tier} risk
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm mt-1">
                      {t.customer_code ? (
                        <Link href={`/workspace/${t.customer_code}`} className="text-brand-600 underline">
                          {display}
                        </Link>
                      ) : (
                        display
                      )}
                      <span className="text-slate-400"> · {t.assigned_queue}</span>
                    </p>
                  </div>
                </div>

                <div className="mt-3 grid md:grid-cols-3 gap-3 text-sm">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">AI recommendation</p>
                    {rr != null ? (
                      <div className="space-y-0.5">
                        <div>
                          {formatPercent(rr)} · {inst ?? "—"} installments
                        </div>
                        {ev != null && <div>EV {formatCurrency(ev)}</div>}
                        {payload.solver_status != null && (
                          <div className="text-xs text-slate-400">Solver: {String(payload.solver_status)}</div>
                        )}
                      </div>
                    ) : (
                      <span className="text-slate-400">No offer payload</span>
                    )}
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3 md:col-span-2">
                    <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Policy validation</p>
                    <p className="text-slate-700">{policyReason || "—"}</p>
                    {payload.within_limits != null && (
                      <p className="text-xs text-slate-500 mt-1">
                        Within limits: {String(payload.within_limits)}
                        {payload.guardrail_status ? ` · Guardrail: ${String(payload.guardrail_status)}` : ""}
                      </p>
                    )}
                    {payload.customer_explanation != null && (
                      <p className="text-xs text-slate-500 mt-2">{String(payload.customer_explanation)}</p>
                    )}
                  </div>
                </div>

                {(t.status === "open" || t.status === "pending_approval" || t.status === "escalated") && (
                  <div className="mt-3 space-y-2">
                    <input
                      className="w-full text-xs border border-slate-200 rounded px-2 py-1.5"
                      placeholder="Resolution note"
                      value={note[t.task_id] || ""}
                      onChange={(e) => setNote((prev) => ({ ...prev, [t.task_id]: e.target.value }))}
                    />
                    <div className="flex flex-wrap gap-1">
                      {canApprove && (
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
                      {canApprove && (
                        <>
                          <Button variant="ghost" size="sm" onClick={() => update(t.task_id, "acknowledged")}>
                            Acknowledge
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => update(t.task_id, "resolved")}>
                            Resolve
                          </Button>
                        </>
                      )}
                      {!canApprove && (
                        <p className="text-xs text-slate-500">Only managers and admins can action approvals.</p>
                      )}
                    </div>
                  </div>
                )}

                {t.resolved_by && (
                  <div className="mt-2 text-[10px] text-slate-400">
                    by {t.resolved_by}
                    {t.resolution_note ? ` — ${t.resolution_note}` : ""}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
