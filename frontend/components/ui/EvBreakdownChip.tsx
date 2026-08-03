import { formatCurrency, formatPercent } from "@/lib/format";
import { ModelValue, type ConfidenceMeta } from "./ConfidenceBadge";

export function EvBreakdownChip({
  pApp,
  pAccept,
  pFulfill,
  amount,
  ev,
  confidence,
}: {
  pApp: number;
  pAccept: number;
  pFulfill: number;
  amount: number;
  ev: number;
  confidence: ConfidenceMeta;
}) {
  return (
    <div className="inline-flex flex-col gap-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs max-w-md">
      <p className="font-semibold text-slate-800">EV = PoAPP × PoA × PoF × Amount</p>
      <p className="text-slate-600 font-mono">
        {formatPercent(pApp)} × {formatPercent(pAccept)} × {formatPercent(pFulfill)} × {formatCurrency(amount)}
      </p>
      <p className="text-slate-900 font-semibold flex items-center gap-1.5">
        = <ModelValue value={formatCurrency(ev)} confidence={confidence} />
      </p>
    </div>
  );
}
