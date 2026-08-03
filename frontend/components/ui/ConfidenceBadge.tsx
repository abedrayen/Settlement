"use client";

import type { ReactNode } from "react";
import clsx from "clsx";

export type ConfidenceMeta = {
  pStd?: number;
  mipGap?: number;
  vintage?: string;
  ood?: boolean;
  modelVersion?: string;
};

export function ConfidenceBadge({ meta }: { meta: ConfidenceMeta }) {
  const level = meta.ood ? "warning" : meta.mipGap && meta.mipGap > 0.01 ? "caution" : "ok";
  return (
    <span className="group relative inline-flex items-center">
      <span
        className={clsx(
          "inline-block w-2 h-2 rounded-full cursor-help",
          level === "warning" && "bg-amber-500",
          level === "caution" && "bg-orange-400",
          level === "ok" && "bg-emerald-500",
        )}
        title="Model confidence"
      />
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 rounded-lg bg-slate-900 text-white text-[10px] p-2 opacity-0 group-hover:opacity-100 transition-opacity z-50 shadow-lg">
        {meta.pStd !== undefined && <div>P(x) std: {meta.pStd.toFixed(3)}</div>}
        {meta.mipGap !== undefined && <div>MIP gap: {(meta.mipGap * 100).toFixed(2)}%</div>}
        {meta.vintage && <div>Vintage: {meta.vintage}</div>}
        {meta.modelVersion && <div>Model: {meta.modelVersion}</div>}
        {meta.ood && <div className="text-amber-300">Out-of-distribution flag</div>}
      </span>
    </span>
  );
}

export function ModelValue({
  value,
  confidence,
  className,
}: {
  value: ReactNode;
  confidence: ConfidenceMeta;
  className?: string;
}) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5", className)}>
      <span>{value}</span>
      <ConfidenceBadge meta={confidence} />
    </span>
  );
}
