"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useRole } from "@/components/AuthProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/LoadingState";
import { GuardrailTag } from "@/components/ui/GuardrailTag";
import { EvBreakdownChip } from "@/components/ui/EvBreakdownChip";
import { ModelValue } from "@/components/ui/ConfidenceBadge";
import { AskAgentBridge } from "@/components/ui/DownloadableTable";
import { DownloadableTable } from "@/components/ui/DownloadableTable";

type Borrower = {
  customer_code: number;
  settlement_code: number;
  customer: Record<string, unknown>;
  settlement: Record<string, unknown>;
  recommended_offer: Record<string, unknown> | null;
  guardrails: { status: string; reason?: string; checks?: string[] };
  applications_summary: { count: number; latest_status?: string; latest_stage?: string };
  payments_summary: { count_6m: number; total_6m: number; latest_date?: string };
  activities_summary?: { count: number; latest_type?: string; latest_date?: string };
};

export default function BorrowerPage({ params }: { params: { id: string } }) {
  const [borrower, setBorrower] = useState<Borrower | null>(null);
  const [offers, setOffers] = useState<{ grid: Array<Record<string, unknown>> } | null>(null);
  const [explain, setExplain] = useState<{ top_positive: Array<{ feature_name: string; shap_value: number }>; top_negative: Array<{ feature_name: string; shap_value: number }> } | null>(null);
  const [showShap, setShowShap] = useState(false);
  const router = useRouter();
  const { role } = useRole();
  const id = params.id;

  useEffect(() => {
    apiGet<Borrower>(`/api/borrowers/${id}`, role).then(setBorrower).catch(console.error);
    apiGet<{ grid: Array<Record<string, unknown>> }>(`/api/borrowers/${id}/offers`, role).then(setOffers).catch(console.error);
    apiGet<typeof explain>(`/api/borrowers/${id}/explain`, role).then(setExplain).catch(console.error);
  }, [id, role]);

  if (!borrower) return <LoadingState message={`Loading borrower ${id}...`} />;

  const rec = borrower.recommended_offer;
  const settlementAmount = Number(borrower.settlement.settlement_amount || borrower.settlement.total_balance_connected_loans || 0);
  const confidence = {
    mipGap: Number(rec?.mip_gap || 0.002),
    vintage: String(borrower.settlement.ref_year_month || "—"),
    modelVersion: String(rec?.model_version || "—"),
    ood: Boolean(borrower.customer.ood_flag),
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={String(borrower.customer.legal_name || `Borrower ${borrower.customer_code}`)}
        description={`Customer ${borrower.customer_code} · Settlement ${borrower.settlement_code} · ${String(borrower.customer.segment)} · ${String(borrower.settlement.settlement_status || "Active")}`}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => router.push("/borrowers")}>Back to borrowers</Button>
            <AskAgentBridge question={`What is the optimal offer for borrower ${id}?`} />
            <Button size="sm" variant="outline" onClick={() => setShowShap((v) => !v)}>
              {showShap ? "Hide SHAP" : "Explain this score"}
            </Button>
          </>
        }
        badge={<GuardrailTag status={borrower.guardrails?.status || "passed"} reason={borrower.guardrails?.reason} />}
      />

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <h2 className="section-title mb-3">Account summary</h2>
          <dl className="space-y-0 text-sm">
            <div className="flex justify-between border-b border-slate-100 py-2">
              <dt className="text-slate-500">Legal name</dt>
              <dd className="font-medium text-right">{String(borrower.customer.legal_name || "—")}</dd>
            </div>
            <div className="flex justify-between border-b border-slate-100 py-2">
              <dt className="text-slate-500">Customer code</dt>
              <dd className="tabular-nums">{borrower.customer_code}</dd>
            </div>
            <div className="flex justify-between border-b border-slate-100 py-2">
              <dt className="text-slate-500">Balance</dt>
              <dd className="font-medium tabular-nums">£{Number(borrower.settlement.total_balance_connected_loans).toLocaleString()}</dd>
            </div>
            <div className="flex justify-between border-b border-slate-100 py-2">
              <dt className="text-slate-500">Applications</dt>
              <dd>{borrower.applications_summary.count} ({borrower.applications_summary.latest_status || "—"})</dd>
            </div>
            <div className="flex justify-between border-b border-slate-100 py-2">
              <dt className="text-slate-500">Payments (6m)</dt>
              <dd className="tabular-nums">£{borrower.payments_summary.total_6m.toLocaleString()} ({borrower.payments_summary.count_6m})</dd>
            </div>
            <div className="flex justify-between border-b border-slate-100 py-2">
              <dt className="text-slate-500">Latest activity</dt>
              <dd>{borrower.activities_summary?.latest_type || String(borrower.settlement.latest_activity_type || "—")}</dd>
            </div>
            <div className="flex justify-between py-2">
              <dt className="text-slate-500">Vulnerability</dt>
              <dd>{String(borrower.customer.vulnerability_status)}</dd>
            </div>
          </dl>
        </Card>

        {rec && (
          <Card>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">Optimal offer (MILP)</p>
            <p className="text-2xl font-semibold text-slate-900">
              <ModelValue value={`${(rec.optimal_rr as number) * 100}% RR`} confidence={confidence} />
            </p>
            <p className="text-sm text-slate-600 mt-1">{String(rec.optimal_installments)} instalments</p>
            <div className="mt-4">
              <EvBreakdownChip
                pApp={Number(rec.p_application)}
                pAccept={Number(rec.p_acceptance)}
                pFulfill={Number(rec.p_fulfillment)}
                amount={settlementAmount}
                ev={Number(rec.expected_value)}
                confidence={confidence}
              />
            </div>
          </Card>
        )}
      </div>

      <Card>
        <h3 className="section-title mb-2">Guardrail status</h3>
        <GuardrailTag status={borrower.guardrails?.status || "passed"} reason={borrower.guardrails?.reason} />
        <ul className="mt-2 text-xs text-slate-600 list-disc pl-4 space-y-0.5">
          {(borrower.guardrails?.checks || []).map((c) => <li key={c}>{c}</li>)}
        </ul>
      </Card>

      {showShap && explain && (
        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <h3 className="section-title text-emerald-800 mb-2">Top positive drivers</h3>
            {explain.top_positive.map((f) => (
              <div key={f.feature_name} className="flex justify-between text-sm py-1.5 border-b border-slate-100 last:border-0">
                <span className="text-slate-700">{f.feature_name}</span>
                <span className="text-emerald-600 tabular-nums">+{f.shap_value.toFixed(3)}</span>
              </div>
            ))}
          </Card>
          <Card>
            <h3 className="section-title text-red-800 mb-2">Top negative drivers</h3>
            {explain.top_negative.map((f) => (
              <div key={f.feature_name} className="flex justify-between text-sm py-1.5 border-b border-slate-100 last:border-0">
                <span className="text-slate-700">{f.feature_name}</span>
                <span className="text-red-600 tabular-nums">{f.shap_value.toFixed(3)}</span>
              </div>
            ))}
          </Card>
        </div>
      )}

      {offers && (
        <DownloadableTable
          columns={[{ key: "recovery_rate", label: "RR" }, { key: "installments", label: "Inst" }, { key: "expected_value", label: "EV" }]}
          rows={offers.grid as Record<string, unknown>[]}
          exportFilename={`borrower_${id}_offers.csv`}
          askQuestion={`Why did the optimiser choose the best offer for borrower ${id}?`}
        >
          <div className="card overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100">
              <h3 className="section-title">Offer grid comparison</h3>
              <p className="section-sub">PoAPP × PoA × PoF scored alternatives</p>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2.5 text-left font-medium">RR</th>
                  <th className="px-4 py-2.5 text-center font-medium">Inst</th>
                  <th className="px-4 py-2.5 text-center font-medium">EV</th>
                  <th className="px-4 py-2.5 text-center font-medium">PoA</th>
                </tr>
              </thead>
              <tbody>
                {offers.grid.map((g, i) => {
                  const optimal = g.recovery_rate === rec?.optimal_rr && g.installments === rec?.optimal_installments;
                  return (
                    <tr key={i} className={optimal ? "bg-emerald-50/70" : "hover:bg-slate-50/80"}>
                      <td className="px-4 py-2.5">
                        {(g.recovery_rate as number) * 100}% {optimal && <Badge variant="success">Optimal</Badge>}
                      </td>
                      <td className="px-4 py-2.5 text-center tabular-nums">{String(g.installments)}</td>
                      <td className="px-4 py-2.5 text-center font-medium tabular-nums">£{Number(g.expected_value).toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-center tabular-nums">{((g.p_acceptance as number) * 100).toFixed(0)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </DownloadableTable>
      )}
    </div>
  );
}
