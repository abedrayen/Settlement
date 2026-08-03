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

type Kpis = {
  total_expected_value: number;
  total_collections: number;
  total_outstanding_balance?: number;
  realization_rate: number;
  borrower_count: number;
  ev_vs_actual_delta: number;
  realization_trend_delta: number;
};

type Segment = {
  segment: string;
  borrower_count: number;
  total_ev: number;
  avg_p_fulfillment: number;
};

type TsPoint = {
  label: string;
  expected_value: number;
  actual_collections: number;
  realization_rate: number;
};

type Metric = {
  model_name: string;
  metric_name: string;
  metric_value: number;
  baseline_value: number;
  alert_flag: boolean;
};

function formatGbp(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `£${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `£${(n / 1_000).toFixed(1)}k`;
  return `£${n.toLocaleString()}`;
}

function pofBucket(pof: number): { key: string; label: string; variant: "success" | "warning" | "danger" } {
  if (pof >= 0.75) return { key: "high", label: "High PoF", variant: "success" };
  if (pof >= 0.55) return { key: "medium", label: "Medium PoF", variant: "warning" };
  return { key: "low", label: "Low PoF", variant: "danger" };
}

export default function PortfolioPage() {
  const { role } = useRole();
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [timeseries, setTimeseries] = useState<TsPoint[]>([]);
  const [alerts, setAlerts] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!canAccess(role, "portfolio_read")) {
      setLoading(false);
      return;
    }
    Promise.all([
      apiGet<Kpis>("/api/portfolio/kpis", role),
      apiGet<Segment[]>("/api/portfolio/segments", role),
      apiGet<TsPoint[]>("/api/portfolio/timeseries", role),
      canAccess(role, "monitoring_read")
        ? apiGet<{ metrics: Metric[]; alerts: Metric[] }>("/api/monitoring", role)
        : Promise.resolve({ metrics: [], alerts: [] as Metric[] }),
    ])
      .then(([k, s, t, m]) => {
        setKpis(k);
        setSegments(s);
        setTimeseries(t);
        setAlerts(m.alerts || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [role]);

  const segmentChart = useMemo(
    () =>
      [...segments]
        .sort((a, b) => b.total_ev - a.total_ev)
        .map((s) => ({
          segment: s.segment,
          ev: s.total_ev,
          borrowers: s.borrower_count,
          pof: Math.round(s.avg_p_fulfillment * 100),
        })),
    [segments],
  );

  const trendChart = useMemo(
    () =>
      timeseries.map((p) => ({
        label: p.label,
        ev: p.expected_value,
        actual: p.actual_collections,
        realisation: Number((p.realization_rate * 100).toFixed(1)),
      })),
    [timeseries],
  );

  const heatmap = useMemo(
    () =>
      segments.map((s) => {
        const bucket = pofBucket(s.avg_p_fulfillment);
        return { ...s, bucket };
      }),
    [segments],
  );

  if (!canAccess(role, "portfolio_read")) {
    return <p className="text-slate-600">Portfolio Monitoring is available to Operational Managers and Admins.</p>;
  }

  if (loading) return <LoadingState message="Loading portfolio…" />;

  const trendPp = (kpis?.realization_trend_delta || 0) * 100;
  const balance = kpis?.total_outstanding_balance ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Portfolio Monitoring"
        description="KPIs, recovery trend, risk heatmap, and alerts."
        actions={
          <AskAgentBridge question="Which portfolio segments are underperforming on realisation?" />
        }
      />

      {alerts.length > 0 && (
        <Alert variant="warning" title={`${alerts.length} alert(s)`}>
          {alerts.map((a, i) => (
            <span key={i}>
              {a.model_name} {a.metric_name}
              {i < alerts.length - 1 ? " · " : ""}
            </span>
          ))}
        </Alert>
      )}

      {kpis && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KpiCard
            label="Expected value"
            value={formatGbp(kpis.total_expected_value)}
            sub={`${kpis.borrower_count} borrowers`}
            accent="blue"
            icon={<IconChart className="w-4 h-4" />}
          />
          <KpiCard label="Actual collections" value={formatGbp(kpis.total_collections)} accent="emerald" />
          <KpiCard label="EV vs actual" value={formatGbp(kpis.ev_vs_actual_delta)} accent="slate" />
          <KpiCard
            label="Realisation"
            value={`${(kpis.realization_rate * 100).toFixed(1)}%`}
            sub={
              trendPp !== 0
                ? `${trendPp >= 0 ? "+" : ""}${trendPp.toFixed(1)}pp`
                : balance
                  ? `of ${formatGbp(balance)}`
                  : undefined
            }
            accent="amber"
          />
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-3">
        <AskAgentBridge question="Summarize portfolio KPIs and call out risks." />
        <AskAgentBridge question="Show model monitoring alerts for the portfolio." />
        <AskAgentBridge question="What if we cap recovery rate at 50% across the portfolio?" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="EV vs actual">
          <ResponsiveContainer width="100%" height={300}>
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

        <ChartCard title="Realisation rate">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trendChart}>
              <CartesianGrid stroke={chartGridStroke} strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} domain={[0, "auto"]} width={48} />
              <Tooltip
                contentStyle={chartTooltipStyle}
                formatter={(value: number) => [`${value}%`, "Realisation"]}
              />
              <Line
                type="monotone"
                dataKey="realisation"
                name="Realisation"
                stroke={CHART_COLORS.warning}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="Expected value by segment">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={segmentChart} margin={{ left: 8, right: 8 }}>
              <CartesianGrid stroke={chartGridStroke} strokeDasharray="3 3" />
              <XAxis dataKey="segment" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatGbp(Number(v))} width={64} />
              <Tooltip
                contentStyle={chartTooltipStyle}
                formatter={(value: number, name: string) => {
                  if (name === "ev") return [formatGbp(value), "EV"];
                  if (name === "pof") return [`${value}%`, "Avg P(Fulfil)"];
                  return [value, "Borrowers"];
                }}
              />
              <Legend />
              <Bar dataKey="ev" name="EV" fill={CHART_COLORS.primary} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <Card>
          <h3 className="section-title mb-2">Risk heatmap</h3>
          <p className="section-sub mb-3">Segment × PoF risk bucket</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2 text-left">Segment</th>
                <th className="px-3 py-2 text-left">Risk</th>
                <th className="px-3 py-2 text-right">Borrowers</th>
                <th className="px-3 py-2 text-right">EV</th>
              </tr>
            </thead>
            <tbody>
              {heatmap.map((h) => (
                <tr key={h.segment} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">{h.segment}</td>
                  <td className="px-3 py-2">
                    <Badge variant={h.bucket.variant}>{h.bucket.label}</Badge>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{h.borrower_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">£{h.total_ev.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
