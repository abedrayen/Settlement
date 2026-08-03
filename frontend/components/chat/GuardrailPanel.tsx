import { StatusBadge } from "@/components/ui/Badge";
import type { GuardrailData } from "./types";

const CHECK_LABELS: Record<string, string> = {
  not_deceased: "Not deceased",
  not_legal_entity: "Not legal entity",
  rr_bounds: "Recovery rate within 20–80%",
  law_protection: "Law protection check",
  vulnerability_review: "Vulnerability review",
  deceased_check: "Deceased check",
};

export function GuardrailPanel({ guardrails }: { guardrails: GuardrailData }) {
  if (!guardrails.status) return null;

  const variant =
    guardrails.status === "blocked"
      ? "border-red-200 bg-red-50/80"
      : guardrails.status === "warning"
        ? "border-amber-200 bg-amber-50/80"
        : "border-emerald-200 bg-emerald-50/80";

  return (
    <div className={`rounded-xl border px-4 py-3 max-w-lg ${variant}`}>
      <div className="flex items-center gap-2 mb-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Compliance Guardrails</p>
        <StatusBadge status={guardrails.status} />
      </div>

      {guardrails.reason && (
        <p className="text-sm text-slate-700">
          <span className="font-medium">Reason:</span> {guardrails.reason}
        </p>
      )}

      {guardrails.checks && guardrails.checks.length > 0 && (
        <ul className="mt-2 space-y-1">
          {guardrails.checks.map((check) => (
            <li key={check} className="text-xs text-slate-600 flex items-center gap-2">
              <span className="text-emerald-500">✓</span>
              {CHECK_LABELS[check] || check.replace(/_/g, " ")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
