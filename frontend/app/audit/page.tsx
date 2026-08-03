"use client";

import { useEffect, useState } from "react";
import { apiGet, API_URL } from "@/lib/api";
import { useRole } from "@/components/AuthProvider";
import { canAccess } from "@/lib/roles";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, LoadingState } from "@/components/ui/LoadingState";
import { GuardrailTag } from "@/components/ui/GuardrailTag";

type AuditEntry = {
  type: string;
  recommendation_id?: string;
  tool_call_id?: string;
  customer_code?: number;
  tool_name?: string;
  guardrail_passed?: boolean;
  model_version?: string;
  input_payload?: unknown;
  output_payload?: unknown;
  event_payload?: unknown;
  created_at?: string;
  executed_at?: string;
};

export default function AuditPage() {
  const { role } = useRole();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [guardrailOnly, setGuardrailOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (filter) qs.set("event_type", filter);
    if (guardrailOnly) qs.set("guardrail_only", "true");
    apiGet<{ entries: AuditEntry[] }>(`/api/audit?${qs}`, role)
      .then((d) => setEntries(d.entries))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [role, filter, guardrailOnly]);

  const exportAudit = () => {
    window.open(`${API_URL}/api/audit/export?format=csv`, "_blank");
  };

  if (loading) return <LoadingState message="Loading audit trail..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit trail"
        actions={canAccess(role, "audit_export") ? <Button size="sm" onClick={exportAudit}>Export CSV</Button> : undefined}
      />

      <div className="flex flex-wrap gap-2">
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="input-field text-sm w-48">
          <option value="">All tool types</option>
          <option value="offer_optimization">Optimizer</option>
          <option value="offer_grid">Offer grid</option>
          <option value="borrower_lookup">Borrower lookup</option>
          <option value="chat_response">Chat events</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={guardrailOnly} onChange={(e) => setGuardrailOnly(e.target.checked)} />
          Guardrail blocks only
        </label>
      </div>

      {entries.length === 0 ? (
        <EmptyState title="No audit entries" />
      ) : (
        <div className="card divide-y divide-slate-100">
          {entries.map((e) => {
            const id = e.recommendation_id || e.tool_call_id || e.type;
            const ts = e.created_at || e.executed_at || "";
            return (
              <div key={id} className="p-4">
                <button className="w-full text-left" onClick={() => setExpanded(expanded === id ? null : id)}>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <div className="flex items-center gap-2">
                      <Badge variant="info">{e.type}</Badge>
                      {e.tool_name && <span className="font-mono text-xs">{e.tool_name}</span>}
                      {e.customer_code && <span className="font-semibold">Borrower {e.customer_code}</span>}
                      {e.guardrail_passed === false && <GuardrailTag status="blocked" />}
                      {e.model_version && <span className="text-slate-500">{e.model_version}</span>}
                    </div>
                    <span className="text-xs text-slate-500">{ts ? new Date(ts).toLocaleString() : ""}</span>
                  </div>
                </button>
                {expanded === id && (
                  <pre className="mt-3 text-xs bg-slate-50 p-3 rounded-lg overflow-auto max-h-64">
                    {JSON.stringify(e.input_payload || e.output_payload || e.event_payload || e, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
