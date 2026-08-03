"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { useRole } from "@/components/AuthProvider";

type Freshness = {
  ref_year_month: string;
  as_of: string;
  last_refresh_display: string;
  sources: Array<{ name: string; stale: boolean; cadence: string }>;
};

export function DataVintageStrip() {
  const { role } = useRole();
  const [data, setData] = useState<Freshness | null>(null);

  useEffect(() => {
    apiGet<Freshness>("/api/settings/freshness", role).then(setData).catch(() => {});
  }, [role]);

  const stale = data?.sources.some((s) => s.stale);

  return (
    <div className="h-8 shrink-0 border-b border-slate-200 bg-white px-4 flex items-center justify-between text-[11px]">
      <div className="flex items-center gap-2.5 text-slate-600">
        <span className="font-semibold text-slate-800">Data vintage</span>
        <span>As of {data?.as_of || "—"}</span>
        <span className="text-slate-300">·</span>
        <span>Refresh {data?.last_refresh_display || "—"}</span>
        <span className="text-slate-300">·</span>
        <span className="font-mono text-slate-700">{data?.ref_year_month || "—"}</span>
      </div>
      {stale && (
        <span className="text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-md font-medium">
          Stale source
        </span>
      )}
    </div>
  );
}
