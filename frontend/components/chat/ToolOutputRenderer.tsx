import Link from "next/link";
import { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { ChatTable } from "./ChatTable";
import { MarkdownContent } from "./MarkdownContent";
import { formatCurrency, formatPercent } from "@/lib/format";
import type { ToolCall } from "./types";

type Segment = {
  segment: string;
  borrower_count: number;
  total_ev: number;
  avg_p_fulfillment: number;
};

type Metric = {
  model_name: string;
  metric_name: string;
  metric_value: number;
  baseline_value: number;
  alert_flag?: boolean;
  drift?: number;
};

type FrontierPoint = {
  strategy_name: string;
  portfolio_ev: number;
  risk_level: string;
  risk_score?: number;
};

type ShapFeature = {
  feature_name: string;
  shap_value: number;
  direction: string;
};

type ComparisonRow = {
  customer_code: number;
  settlement_code?: number;
  recovery_rate?: number;
  ev_from: number;
  ev_to: number;
  ev_delta: number;
};

function PortfolioOutput({ data }: { data: Record<string, unknown> }) {
  const kpis = (data.kpis || {}) as Record<string, number>;
  const segments = (data.segments || []) as Segment[];

  return (
    <div className="space-y-3 max-w-2xl">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[
          { label: "Portfolio EV", value: formatCurrency(kpis.total_expected_value || 0) },
          { label: "Collections", value: formatCurrency(kpis.total_collections || 0) },
          { label: "Realization", value: formatPercent(kpis.realization_rate || 0, 1) },
          { label: "Borrowers", value: String(kpis.borrower_count || 0) },
        ].map((kpi) => (
          <div key={kpi.label} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <p className="text-xs text-slate-500">{kpi.label}</p>
            <p className="text-sm font-bold text-slate-900 mt-0.5">{kpi.value}</p>
          </div>
        ))}
      </div>

      <ChatTable
        title="Segment Performance"
        columns={[
          { key: "segment", label: "Segment" },
          { key: "borrowers", label: "Borrowers", align: "center" },
          { key: "ev", label: "Total EV", align: "right" },
          { key: "fulfill", label: "Avg P(Fulfill)", align: "right" },
        ]}
        rows={segments.map((s) => ({
          key: s.segment,
          cells: {
            segment: <span className="font-medium">{s.segment}</span>,
            borrowers: s.borrower_count,
            ev: formatCurrency(s.total_ev),
            fulfill: formatPercent(s.avg_p_fulfillment),
          },
        }))}
      />
    </div>
  );
}

function MonitoringOutput({ data }: { data: Record<string, unknown> }) {
  const metrics = (data.metrics || []) as Metric[];

  return (
    <ChatTable
      title="Model Health Metrics"
      columns={[
        { key: "model", label: "Model" },
        { key: "metric", label: "Metric" },
        { key: "value", label: "Value", align: "right" },
        { key: "baseline", label: "Baseline", align: "right" },
        { key: "status", label: "Status", align: "center" },
      ]}
      rows={metrics.map((m, i) => ({
        key: `${m.model_name}-${m.metric_name}-${i}`,
        highlight: !!m.alert_flag,
        cells: {
          model: m.model_name,
          metric: m.metric_name,
          value: String(m.metric_value),
          baseline: String(m.baseline_value),
          status: m.alert_flag ? (
            <Badge variant="danger">Alert</Badge>
          ) : (
            <Badge variant="success">OK</Badge>
          ),
        },
      }))}
    />
  );
}

function FrontierOutput({ data }: { data: Record<string, unknown> }) {
  const frontier = (data.frontier || []) as FrontierPoint[];
  const opt = (data.optimization || data.simulation || {}) as Record<string, unknown>;

  return (
    <div className="space-y-3 max-w-2xl">
      <ChatTable
        title="Efficient Frontier"
        columns={[
          { key: "strategy", label: "Strategy" },
          { key: "ev", label: "Portfolio EV", align: "right" },
          { key: "risk", label: "Risk Level", align: "center" },
        ]}
        rows={frontier.map((f) => ({
          key: f.strategy_name,
          cells: {
            strategy: <span className="font-medium">{f.strategy_name}</span>,
            ev: formatCurrency(f.portfolio_ev),
            risk: f.risk_level,
          },
        }))}
      />

      {opt.baseline_portfolio_ev != null && (
        <div className="rounded-lg border border-blue-200 bg-blue-50/80 px-4 py-3 text-sm text-blue-900">
          <p className="font-medium">Portfolio optimization</p>
          <p className="mt-1 text-xs text-blue-800">
            Portfolio EV {formatCurrency(Number(opt.baseline_portfolio_ev))} →{" "}
            {formatCurrency(Number(opt.constrained_portfolio_ev))}
            {opt.ev_change_percent != null && ` (${opt.ev_change_percent}% change)`}
            {opt.solver_status != null && ` · ${String(opt.solver_status)}`}
          </p>
        </div>
      )}
    </div>
  );
}

function InstallmentComparisonOutput({ data }: { data: ComparisonRow[] }) {
  return (
    <ChatTable
      title="Installment Comparison (2 → 1)"
      columns={[
        { key: "rank", label: "#", align: "center" },
        { key: "customer", label: "Customer" },
        { key: "from", label: "EV (2 inst)", align: "right" },
        { key: "to", label: "EV (1 inst)", align: "right" },
        { key: "delta", label: "Δ EV", align: "right" },
      ]}
      rows={data.map((row, i) => ({
        key: String(row.customer_code),
        cells: {
          rank: i + 1,
          customer: (
            <Link href={`/workspace/${row.customer_code}`} className="text-blue-600 hover:underline font-medium">
              {row.customer_code}
            </Link>
          ),
          from: formatCurrency(row.ev_from),
          to: formatCurrency(row.ev_to),
          delta: <span className="text-emerald-700 font-semibold">+{formatCurrency(row.ev_delta)}</span>,
        },
      }))}
    />
  );
}

function ExplainabilityOutput({ data }: { data: Record<string, unknown> }) {
  const positive = (data.top_positive || []) as ShapFeature[];
  const negative = (data.top_negative || []) as ShapFeature[];

  if (!positive.length && !negative.length) return null;

  return (
    <div className="grid sm:grid-cols-2 gap-3 max-w-2xl">
      <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3">
        <p className="text-xs font-semibold text-emerald-800 uppercase tracking-wide mb-2">Top Positive Drivers</p>
        <ul className="space-y-1.5">
          {positive.map((f) => (
            <li key={f.feature_name} className="flex justify-between text-xs">
              <span className="text-slate-700">{f.feature_name}</span>
              <span className="font-mono text-emerald-600">+{f.shap_value.toFixed(3)}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="rounded-xl border border-red-200 bg-red-50/50 p-3">
        <p className="text-xs font-semibold text-red-800 uppercase tracking-wide mb-2">Top Negative Drivers</p>
        <ul className="space-y-1.5">
          {negative.map((f) => (
            <li key={f.feature_name} className="flex justify-between text-xs">
              <span className="text-slate-700">{f.feature_name}</span>
              <span className="font-mono text-red-600">{f.shap_value.toFixed(3)}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function DocumentRagOutput({ data }: { data: Record<string, unknown> }) {
  const sources = (data.sources || []) as Array<{ document_name: string; content: string; score: number }>;
  if (!sources.length) return null;

  return (
    <div className="space-y-3 max-w-2xl">
      {sources.map((s, i) => (
        <div key={i} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between gap-2 mb-2">
            <p className="text-sm font-semibold text-slate-900">{s.document_name}</p>
            <span className="text-xs text-slate-400">relevance {s.score.toFixed(2)}</span>
          </div>
          <MarkdownContent content={s.content.slice(0, 600) + (s.content.length > 600 ? "…" : "")} />
        </div>
      ))}
    </div>
  );
}

function BorrowerLookupOutput({ data }: { data: Record<string, unknown> }) {
  const customer = (data.customer || {}) as Record<string, unknown>;
  const settlement = (data.settlement || {}) as Record<string, unknown>;
  const customerCode = data.customer_code as number;

  const fields: [string, string][] = [
    ["Segment", String(customer.segment ?? "—")],
    ["Region", String(customer.region ?? "—")],
    ["Vulnerability", String(customer.vulnerability_status ?? "—")],
    ["Balance", formatCurrency(Number(settlement.total_balance_connected_loans || 0))],
    ["Deceased", customer.flag_deceased === 1 ? "Yes" : "No"],
    ["Legal Entity", customer.flag_legal_entity === 1 ? "Yes" : "No"],
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 max-w-md">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Borrower Profile</p>
        {customerCode && (
          <Link href={`/workspace/${customerCode}`} className="text-xs text-blue-600 hover:underline">
            Full details →
          </Link>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        {fields.map(([label, val]) => (
          <div key={label} className="contents">
            <dt className="text-slate-500">{label}</dt>
            <dd className="font-medium text-slate-800 text-right">{val}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const RENDER_ORDER = [
  "portfolio_analytics",
  "monitoring",
  "frontier_analysis",
  "installment_comparison",
  "explainability",
  "document_rag",
  "borrower_lookup",
  "offer_grid",
  "offer_optimization",
] as const;

export function ToolOutputRenderer({
  toolCalls,
  hasRecommendation,
}: {
  toolCalls: ToolCall[];
  hasRecommendation: boolean;
}) {
  const byTool = new Map<string, unknown>();
  for (const tc of toolCalls) {
    if (tc.output != null) {
      byTool.set(tc.tool, tc.output);
    }
  }

  const blocks: ReactNode[] = [];

  for (const tool of RENDER_ORDER) {
    const output = byTool.get(tool);
    if (output == null) continue;

    if (tool === "offer_optimization" && hasRecommendation) continue;

    switch (tool) {
      case "portfolio_analytics":
        blocks.push(<PortfolioOutput key={tool} data={output as Record<string, unknown>} />);
        break;
      case "monitoring":
        blocks.push(<MonitoringOutput key={tool} data={output as Record<string, unknown>} />);
        break;
      case "frontier_analysis":
        blocks.push(<FrontierOutput key={tool} data={output as Record<string, unknown>} />);
        break;
      case "installment_comparison":
        blocks.push(<InstallmentComparisonOutput key={tool} data={output as ComparisonRow[]} />);
        break;
      case "explainability":
        blocks.push(<ExplainabilityOutput key={tool} data={output as Record<string, unknown>} />);
        break;
      case "document_rag":
        blocks.push(<DocumentRagOutput key={tool} data={output as Record<string, unknown>} />);
        break;
      case "borrower_lookup":
        blocks.push(<BorrowerLookupOutput key={tool} data={output as Record<string, unknown>} />);
        break;
      case "offer_grid": {
        const gridData = output as { grid?: Array<Record<string, unknown>> };
        const grid = gridData.grid || [];
        if (grid.length) {
          blocks.push(
            <ChatTable
              key={tool}
              title="Offer Grid Comparison"
              columns={[
                { key: "rr", label: "Recovery Rate" },
                { key: "inst", label: "Installments", align: "center" },
                { key: "ev", label: "EV", align: "center" },
                { key: "pa", label: "P(Accept)", align: "center" },
              ]}
              rows={grid.map((g, i) => ({
                key: String(i),
                cells: {
                  rr: `${((g.recovery_rate as number) * 100).toFixed(0)}%`,
                  inst: String(g.installments),
                  ev: formatCurrency(Number(g.expected_value)),
                  pa: formatPercent(Number(g.p_acceptance)),
                },
              }))}
            />,
          );
        }
        break;
      }
      default:
        break;
    }
  }

  if (!blocks.length) return null;

  return <div className="space-y-3">{blocks}</div>;
}
