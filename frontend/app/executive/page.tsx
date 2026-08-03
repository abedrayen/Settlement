"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet } from "@/lib/api";
import { useRole } from "@/components/AuthProvider";
import { canAccess } from "@/lib/roles";
import { PageHeader } from "@/components/ui/PageHeader";
import { KpiCard } from "@/components/ui/KpiCard";
import { ChartCard, Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { AskAgentBridge } from "@/components/ui/DownloadableTable";
import { chartGridStroke, chartTooltipStyle, CHART_COLORS } from "@/lib/chartTheme";
import { IconChart } from "@/components/icons";

type ExecutiveKpis = {
  recovery_rate: number;
  automation_ratio: number;
  portfolio_exposure: number;
  total_expected_value: number;
  total_collections: number;
  ev_vs_actual_delta: number;
  borrower_count: number;
  risk_segmentation: Array<{
    segment: string;
    borrower_count: number;
    total_ev: number;
    avg_p_fulfillment: number;
  }>;
  risk_heatmap: Array<{
    segment: string;
    bucket: string;
    borrower_count: number;
    total_ev: number;
    avg_p_fulfillment: number;
  }>;
  workflow_bottlenecks: {
    open_by_queue: Record<string, number>;
    oldest: Array<{ task_id: string; queue: string; status: string; age_hours: number; reason?: string }>;
    open_count: number;
  };
  policy_effectiveness: {
    passed: number;
    warnings: number;
    blocks: number;
    hitl_required: number;
    total_recommendations: number;
  };
  forecasted_recoveries: Array<{ label: string; forecasted_ev: number; forecasted_collections: number }>;
  timeseries: Array<{
    label: string;
    expected_value: number;
    actual_collections: number;
    realization_rate: number;
  }>;
  alerts: Array<{ model_name: string; metric_name: string; metric_value: number; baseline_value: number }>;
};

function formatGbp(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `£${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `£${(n / 1_000).toFixed(1)}k`;
  return `£${n.toLocaleString()}`;
}

const BUCKET_LABEL: Record<string, string> = {
  high_pof: "High PoF",
  medium_pof: "Medium PoF",
  low_pof: "Low PoF",
};

export default function ExecutivePage() {
  const { role } = useRole();
  const [data, setData] = useState<ExecutiveKpis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!canAccess(role, "executive_read")) {
      setLoading(false);
      return;
    }
    apiGet<ExecutiveKpis>("/api/executive/kpis", role)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [role]);

  const trendChart = useMemo(
    () =>
      (data?.timeseries || []).map((p) => ({
        label: p.label,
        ev: p.expected_value,
        actual: p.actual_collections,
        realisation: Number((p.realization_rate * 100).toFixed(1)),
      })),
    [data],
  );

  const forecastChart = useMemo(
    () =>
      (data?.forecasted_recoveries || []).map((f) => ({
        label: f.label,
        ev: f.forecasted_ev,
        collections: f.forecasted_collections,
      })),
    [data],
  );

  const segmentChart = useMemo(
    () =>
      [...(data?.risk_segmentation || [])]
        .sort((a, b) => b.total_ev - a.total_ev)
        .map((s) => ({
          segment: s.segment,
          ev: s.total_ev,
          pof: Math.round(s.avg_p_fulfillment * 100),
        })),
    [data],
  );

  if (!canAccess(role, "executive_read")) {
    return <p className="text-slate-600">Executive Dashboard is available to Operational Managers and Admins.</p>;
  }

  if (loading || !data) return <LoadingState message="Loading executive dashboard…" />;

  const policy = data.policy_effectiveness;
  const bottlenecks = Object.entries(data.workflow_bottlenecks.open_by_queue);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Executive Dashboard"
        description="Strategic recovery, automation, exposure, and workflow health."
        actions={<AskAgentBridge question="Summarize portfolio performance and key risks this month." />}
      />

      {data.alerts?.length > 0 && (
        <Alert variant="warning" title={`${data.alerts.length} model alert(s)`}>
          {data.alerts
            .slice(0, 3)
            .map((a) => `${a.model_name} ${a.metric_name}`)
            .join(" · ")}
        </Alert>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Recovery rate"
          value={`${((data.recovery_rate || 0) * 100).toFixed(1)}%`}
          accent="emerald"
          icon={<IconChart className="w-4 h-4" />}
        />
        <KpiCard
          label="Automation ratio"
          value={`${(data.automation_ratio * 100).toFixed(0)}%`}
          sub="Auto-cleared vs HITL"
          accent="blue"
        />
        <KpiCard label="Portfolio exposure" value={formatGbp(data.portfolio_exposure)} accent="amber" />
        <KpiCard
          label="EV vs actual"
          value={formatGbp(data.ev_vs_actual_delta)}
          sub={`${data.borrower_count} borrowers`}
          accent="slate"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="Recovery trend">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trendChart}>
              <CartesianGrid stroke={chartGridStroke} strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatGbp(Number(v))} width={64} />
              <Tooltip
                contentStyle={chartTooltipStyle}
                formatter={(value: number, name: string) => [
                  name === "realisation" ? `${value}%` : formatGbp(value),
                  name === "ev" ? "EV" : name === "actual" ? "Actual" : "Realisation",
                ]}
              />
              <Legend />
              <Line type="monotone" dataKey="ev" name="EV" stroke={CHART_COLORS.primary} strokeWidth={2} dot={false} />
              <Line
                type="monotone"
                dataKey="actual"
                name="Actual"
                stroke={CHART_COLORS.success}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Forecasted recoveries">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={forecastChart}>
              <CartesianGrid stroke={chartGridStroke} strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatGbp(Number(v))} width={64} />
              <Tooltip
                contentStyle={chartTooltipStyle}
                formatter={(value: number, name: string) => [
                  formatGbp(value),
                  name === "ev" ? "Forecast EV" : "Forecast collections",
                ]}
              />
              <Legend />
              <Line type="monotone" dataKey="ev" name="Forecast EV" stroke={CHART_COLORS.primary} strokeWidth={2} />
              <Line
                type="monotone"
                dataKey="collections"
                name="Forecast collections"
                stroke={CHART_COLORS.warning}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="Risk segmentation (EV by segment)">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={segmentChart}>
              <CartesianGrid stroke={chartGridStroke} strokeDasharray="3 3" />
              <XAxis dataKey="segment" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatGbp(Number(v))} width={64} />
              <Tooltip contentStyle={chartTooltipStyle} formatter={(v: number) => formatGbp(v)} />
              <Bar dataKey="ev" name="EV" fill={CHART_COLORS.primary} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <Card>
          <h3 className="section-title mb-2">Risk heatmap</h3>
          <p className="section-sub mb-3">Segment × fulfilment probability bucket</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                  <th className="px-3 py-2 text-left">Segment</th>
                  <th className="px-3 py-2 text-left">Bucket</th>
                  <th className="px-3 py-2 text-right">Borrowers</th>
                  <th className="px-3 py-2 text-right">EV</th>
                </tr>
              </thead>
              <tbody>
                {data.risk_heatmap.map((h) => (
                  <tr key={`${h.segment}-${h.bucket}`} className="border-t border-slate-100">
                    <td className="px-3 py-2 font-medium">{h.segment}</td>
                    <td className="px-3 py-2">
                      <Badge
                        variant={
                          h.bucket === "high_pof" ? "success" : h.bucket === "medium_pof" ? "warning" : "danger"
                        }
                      >
                        {BUCKET_LABEL[h.bucket] || h.bucket}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{h.borrower_count}</td>
                    <td className="px-3 py-2 text-right tabular-nums">£{Number(h.total_ev).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="section-title mb-2">Workflow bottlenecks</h3>
          <p className="section-sub mb-3">{data.workflow_bottlenecks.open_count} open items</p>
          {bottlenecks.length === 0 ? (
            <p className="text-sm text-slate-500">No open workflow queues.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {bottlenecks.map(([queue, count]) => (
                <li key={queue} className="flex justify-between border-b border-slate-100 py-1.5">
                  <span>{queue}</span>
                  <span className="tabular-nums font-medium">{count}</span>
                </li>
              ))}
            </ul>
          )}
          {data.workflow_bottlenecks.oldest.slice(0, 3).map((o) => (
            <p key={o.task_id} className="text-xs text-slate-500 mt-2">
              Oldest: {o.queue} · {o.age_hours}h · {o.reason || o.status}
            </p>
          ))}
        </Card>

        <Card>
          <h3 className="section-title mb-2">Policy effectiveness</h3>
          <p className="section-sub mb-3">{policy.total_recommendations} scored recommendations</p>
          <dl className="text-sm space-y-2">
            <div className="flex justify-between">
              <dt className="text-slate-500">Guardrail passed</dt>
              <dd className="tabular-nums font-medium">{policy.passed}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Pending / warning HITL</dt>
              <dd className="tabular-nums font-medium">{policy.warnings}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Specialist blocks</dt>
              <dd className="tabular-nums font-medium">{policy.blocks}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">HITL required</dt>
              <dd className="tabular-nums font-medium">{policy.hitl_required}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
