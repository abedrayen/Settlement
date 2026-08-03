import clsx from "clsx";

export function GuardrailTag({
  status,
  reason,
}: {
  status: "passed" | "blocked" | "warning" | string;
  reason?: string;
}) {
  const variant =
    status === "passed" ? "passed" : status === "warning" ? "warning" : "blocked";
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full",
        variant === "passed" && "bg-emerald-100 text-emerald-800",
        variant === "warning" && "bg-amber-100 text-amber-800",
        variant === "blocked" && "bg-red-100 text-red-800",
      )}
      title={reason}
    >
      Guardrail: {variant === "passed" ? "passed" : variant === "warning" ? "warning" : "blocked"}
    </span>
  );
}
