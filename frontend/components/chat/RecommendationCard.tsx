import Link from "next/link";
import { formatCurrency, formatPercent } from "@/lib/format";
import { ModelValue } from "@/components/ui/ConfidenceBadge";
import { EvBreakdownChip } from "@/components/ui/EvBreakdownChip";
import { GuardrailTag } from "@/components/ui/GuardrailTag";
import { Badge } from "@/components/ui/Badge";

export function RecommendationCard({ data }: { data: Record<string, unknown> }) {
  const customerCode = data.customer_code as number;
  const legalName = data.legal_name as string | undefined;
  const display =
    (data.display_name as string | undefined) ||
    (legalName && customerCode ? `${legalName} (${customerCode})` : customerCode ? String(customerCode) : "Borrower");
  const rr = data.recommended_rr as number;
  const installments = data.recommended_installments as number;
  const confidence = {
    mipGap: Number(data.mip_gap || 0),
    vintage: String(data.ref_year_month || data.vintage || "—"),
    modelVersion: String(data.model_version || "—"),
  };
  const amount = Number(data.settlement_amount || 10000);
  const requiresApproval = Boolean(data.requires_approval);
  const riskTier = String(data.risk_tier || "low");
  const solver = String(data.solver_status || "Optimal");

  return (
    <div className="rounded-xl border border-emerald-200/80 bg-gradient-to-br from-emerald-50 to-white p-4 max-w-lg space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="font-semibold text-emerald-800 text-sm">Optimal Settlement Offer</p>
        <div className="flex items-center gap-1.5 flex-wrap">
          {data.guardrail_passed !== false ? (
            <GuardrailTag status="passed" />
          ) : (
            <GuardrailTag status="blocked" />
          )}
          {requiresApproval && <Badge variant="warning">Needs approval</Badge>}
          <Badge variant={riskTier === "high" ? "danger" : riskTier === "medium" ? "warning" : "info"}>
            {riskTier}
          </Badge>
        </div>
      </div>

      <div className="text-xs text-emerald-800 font-medium">{display}</div>

      <div className="flex items-baseline gap-3">
        <ModelValue
          value={<span className="text-3xl font-bold text-emerald-700">{formatPercent(rr)}</span>}
          confidence={confidence}
        />
        <span className="text-sm text-emerald-600">{installments} installments</span>
      </div>

      <EvBreakdownChip
        pApp={Number(data.p_application)}
        pAccept={Number(data.p_acceptance)}
        pFulfill={Number(data.p_fulfillment)}
        amount={amount}
        ev={Number(data.expected_value)}
        confidence={confidence}
      />

      <div className="flex items-center justify-between text-[11px] text-slate-500">
        <span>
          Solver: {solver}
          {data.optimizer ? ` (${String(data.optimizer)})` : ""}
        </span>
        {customerCode && (
          <Link href={`/borrowers/${customerCode}`} className="text-emerald-700 underline">
            View borrower →
          </Link>
        )}
      </div>

      {requiresApproval && data.approver_queue && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-2 py-1.5">
          Routed to <strong>{String(data.approver_queue).replace(/_/g, " ")}</strong>
          {data.approval_reason ? ` — ${String(data.approval_reason)}` : ""}
        </p>
      )}
    </div>
  );
}
