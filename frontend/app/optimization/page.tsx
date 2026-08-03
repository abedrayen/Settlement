"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { apiGet } from "@/lib/api";
import { useRole } from "@/components/AuthProvider";
import { canAccess } from "@/lib/roles";
import { PageHeader } from "@/components/ui/PageHeader";
import { KpiCard } from "@/components/ui/KpiCard";
import { ChartCard, Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/LoadingState";
import { AskAgentBridge, DownloadableTable } from "@/components/ui/DownloadableTable";
import { chartGridStroke, chartTooltipStyle, CHART_COLORS } from "@/lib/chartTheme";
import { IconChart } from "@/components/icons";

type FrontierPoint = {
  strategy_name: string;
  portfolio_ev: number;
  risk_level: string;
  risk_score: number;
};

type OptimizationResult = {
  baseline_portfolio_ev: number;
  constrained_portfolio_ev: number;
  ev_change_percent: number;
  borrowers_affected: number;
  avg_rr: number;
  solver_status: string;
  mip_gap: number | null;
  optimizer: string;
  constraints: Record<string, unknown>;
};

type BorrowerOpt = {
  customer_code: number;
  legal_name?: string;
  expected_value?: number | null;
  optimal_rr?: number | null;
  p_fulfillment?: number | null;
};

function formatGbp(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `£${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `£${(n / 1_000).toFixed(1)}k`;
  return `£${n.toLocaleString()}`;
}

export default function OptimizationPage() {
  const { role } = useRole();
  const canRun = canAccess(role, "strategy_run");
  const [frontier, setFrontier] = useState<FrontierPoint[]>([]);
  const [optimization, setOptimization] = useState<OptimizationResult | null>(null);
  const [minPf, setMinPf] = useState(0.7);
  const [maxRr, setMaxRr] = useState(0.8);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [topOffers, setTopOffers] = useState<BorrowerOpt[]>([]);

  const loadFrontier = useCallback(
    async (pof: number, rr: number) => {
      const d = await apiGet<{ frontier: FrontierPoint[]; optimization: OptimizationResult }>(
        `/api/frontier?min_p_fulfill=${pof}&max_rr=${rr}`,
        role,
      );
      setFrontier(d.frontier || []);
      setOptimization(d.optimization || null);
    },
    [role],
  );

  const runOptimization = async () => {
    if (!canRun) return;
    setRunning(true);
    setError(null);
    try {
      await loadFrontier(minPf, maxRr);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Optimization failed");
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    Promise.all([
      loadFrontier(minPf, maxRr),
      apiGet<BorrowerOpt[]>("/api/borrowers", role),
    ])
      .then(([, borrowers]) => {
        setTopOffers(
          [...borrowers]
            .filter((b) => b.expected_value != null)
            .sort((a, b) => Number(b.expected_value) - Number(a.expected_value))
            .slice(0, 8),
        );
      })
      .catch((e) => {
        console.error(e);
        setError(e instanceof Error ? e.message : "Failed to load optimization data");
      })
      .finally(() => setLoading(false));
    // Initial load only — subsequent runs use the CTA
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  if (loading) return <LoadingState message="Loading settlement optimization…" />;

  const baseline = Number(optimization?.baseline_portfolio_ev || 0);
  const constrained = Number(optimization?.constrained_portfolio_ev || 0);
  const delta = constrained - baseline;
  const deltaPct = Number(optimization?.ev_change_percent || 0);
  const best = frontier.length
    ? [...frontier].sort((a, b) => b.portfolio_ev - a.portfolio_ev)[0]
    : null;

  const chartData = frontier.map((f) => ({
    name: f.strategy_name,
    risk: f.risk_score * 100,
    ev: f.portfolio_ev / 1_000_000,
    isBest: best?.strategy_name === f.strategy_name,
  }));
  const referencePoints = chartData.filter((d) => !d.isBest);
  const bestPoints = chartData.filter((d) => d.isBest);

  const constraints = optimization?.constraints || {};
  const constraintLabels = [
    constraints.min_p_fulfill != null ? `PoF ≥ ${(Number(constraints.min_p_fulfill) * 100).toFixed(0)}%` : null,
    constraints.max_rr != null ? `Max RR ${(Number(constraints.max_rr) * 100).toFixed(0)}%` : null,
    constraints.max_avg_rr != null ? `Max avg RR ${(Number(constraints.max_avg_rr) * 100).toFixed(0)}%` : null,
    constraints.max_installment_share != null
      ? `Installment share ≤ ${(Number(constraints.max_installment_share) * 100).toFixed(0)}%`
      : null,
  ].filter(Boolean) as string[];

  const exportRows = topOffers.map((b) => ({
    borrower: `${b.legal_name || b.customer_code} (${b.customer_code})`,
    customer_code: b.customer_code,
    expected_value: Number(b.expected_value || 0),
    optimal_rr: b.optimal_rr != null ? Number(b.optimal_rr) : "",
    p_fulfillment: b.p_fulfillment != null ? Number(b.p_fulfillment) : "",
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settlement Optimization"
        description="Assign settlement offers under policy constraints to maximize portfolio Expected Value (EV)."
        actions={
          <AskAgentBridge
            question={`What is the portfolio EV impact if we require P(Fulfil) >= ${minPf} and cap recovery rate at ${maxRr}?`}
          />
        }
      />

      {error && (
        <Alert variant="danger" title="Optimization error">
          {error}
        </Alert>
      )}

      {best && (
        <Alert variant="success" title="Highest-EV reference strategy">
          {best.strategy_name} · {formatGbp(best.portfolio_ev)} · Risk {best.risk_level}
        </Alert>
      )}

      {optimization && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <KpiCard
            label="Baseline EV"
            value={formatGbp(baseline)}
            sub="Current recommended offers"
            accent="slate"
            icon={<IconChart className="w-4 h-4" />}
          />
          <KpiCard
            label="Optimized EV"
            value={formatGbp(constrained)}
            sub="Under active constraints"
            accent="blue"
          />
          <KpiCard
            label="EV delta"
            value={`${delta >= 0 ? "+" : ""}${formatGbp(delta)}`}
            sub={`${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(2)}%`}
            accent={delta >= 0 ? "emerald" : "amber"}
            trend={{
              value: `${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(2)}%`,
              positive: delta >= 0,
            }}
          />
          <KpiCard
            label="Avg recovery rate"
            value={`${(Number(optimization.avg_rr || 0) * 100).toFixed(1)}%`}
            accent="amber"
          />
          <KpiCard
            label="Borrowers assigned"
            value={String(optimization.borrowers_affected ?? "—")}
            sub="Portfolio MILP assignment"
            accent="emerald"
          />
        </div>
      )}

      <Card padding={false}>
        <div className="p-4 grid md:grid-cols-3 gap-4 items-end">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            PoF floor
            <input
              type="range"
              min={0.5}
              max={0.9}
              step={0.05}
              value={minPf}
              onChange={(e) => setMinPf(Number(e.target.value))}
              className="w-full mt-2"
              disabled={running}
            />
            <span className="font-mono text-sm text-slate-800">{(minPf * 100).toFixed(0)}%</span>
          </label>
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            Max RR
            <input
              type="range"
              min={0.3}
              max={0.9}
              step={0.05}
              value={maxRr}
              onChange={(e) => setMaxRr(Number(e.target.value))}
              className="w-full mt-2"
              disabled={running}
            />
            <span className="font-mono text-sm text-slate-800">{(maxRr * 100).toFixed(0)}%</span>
          </label>
          <div className="space-y-1">
            <Button onClick={runOptimization} disabled={!canRun || running}>
              {running ? "Optimizing…" : "Run portfolio optimization"}
            </Button>
            {!canRun && (
              <p className="text-[11px] text-slate-500">
                Analysts can view results; managers and admins run portfolio MILP under new constraints.
              </p>
            )}
          </div>
        </div>
      </Card>

      {optimization && (
        <div className="card px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Solver</span>
          <Badge variant={optimization.solver_status === "Optimal" ? "success" : "warning"}>
            {optimization.solver_status || "—"}
          </Badge>
          <span className="text-slate-600">
            Engine <span className="font-medium text-slate-800">{optimization.optimizer || "PuLP"}</span>
          </span>
          {optimization.mip_gap != null && (
            <span className="text-slate-600 tabular-nums">
              MIP gap{" "}
              <span className="font-medium text-slate-800">
                {(Number(optimization.mip_gap) * 100).toFixed(2)}%
              </span>
            </span>
          )}
          {constraintLabels.length > 0 && (
            <div className="flex flex-wrap gap-1.5 ml-auto">
              {constraintLabels.map((label) => (
                <Badge key={label} variant="default">
                  {label}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-3">
        <AskAgentBridge
          question={`Explain the portfolio EV change under P(Fulfil) >= ${minPf} and max RR ${maxRr}.`}
        />
        <AskAgentBridge question="Which efficient frontier strategy balances EV and risk best for this portfolio?" />
        <AskAgentBridge question="What happens to total EV if we apply a stricter P(Fulfil) floor of 80%?" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard
          title="Efficient frontier"
          subtitle="Reference strategies (policy curve) — not recomputed by the live MILP run"
        >
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart>
              <CartesianGrid stroke={chartGridStroke} strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="risk"
                name="Risk"
                unit="%"
                tick={{ fontSize: 11 }}
                domain={["auto", "auto"]}
              />
              <YAxis
                type="number"
                dataKey="ev"
                name="EV"
                unit="M"
                tick={{ fontSize: 11 }}
                domain={["auto", "auto"]}
              />
              <ZAxis range={[100, 100]} />
              <Tooltip
                contentStyle={chartTooltipStyle}
                cursor={{ strokeDasharray: "3 3" }}
                formatter={(value: number, name: string) => [
                  name === "ev" ? `£${value.toFixed(2)}M` : `${value.toFixed(0)}%`,
                  name === "ev" ? "EV" : "Risk",
                ]}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.name || ""}
              />
              <Scatter data={referencePoints} fill={CHART_COLORS.primary} name="Reference" />
              <Scatter data={bestPoints} fill={CHART_COLORS.success} name="Best EV" />
            </ScatterChart>
          </ResponsiveContainer>
        </ChartCard>

        <Card padding={false}>
          <div className="px-4 pt-4 pb-2">
            <h3 className="section-title">Strategy comparison</h3>
            <p className="section-sub mb-3">Reference frontier strategies ranked by portfolio EV</p>
          </div>
          <div className="overflow-hidden border-t border-slate-100">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                  <th className="px-3 py-2 text-left font-medium">Strategy</th>
                  <th className="px-3 py-2 text-right font-medium">EV</th>
                  <th className="px-3 py-2 text-left font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {[...frontier]
                  .sort((a, b) => b.portfolio_ev - a.portfolio_ev)
                  .map((f) => {
                    const isBest = best?.strategy_name === f.strategy_name;
                    return (
                      <tr
                        key={f.strategy_name}
                        className={
                          isBest ? "border-t border-slate-100 bg-emerald-50/70" : "border-t border-slate-100"
                        }
                      >
                        <td className="px-3 py-2 font-medium">
                          {f.strategy_name}
                          {isBest && (
                            <Badge variant="success" className="ml-2">
                              Best EV
                            </Badge>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatGbp(f.portfolio_ev)}</td>
                        <td className="px-3 py-2">
                          <Badge
                            variant={
                              f.risk_level === "Low"
                                ? "success"
                                : f.risk_level === "Medium"
                                  ? "warning"
                                  : "danger"
                            }
                          >
                            {f.risk_level}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <DownloadableTable
        columns={[
          { key: "borrower", label: "Borrower" },
          { key: "customer_code", label: "Code" },
          { key: "expected_value", label: "EV" },
          { key: "optimal_rr", label: "Opt RR" },
          { key: "p_fulfillment", label: "PoF" },
        ]}
        rows={exportRows}
        exportFilename="top_borrower_recommendations.csv"
        askQuestion="Which borrowers contribute most to portfolio EV under current recommendations?"
      >
        <Card padding={false}>
          <div className="px-4 pt-4 pb-2">
            <h3 className="section-title">Top borrower recommendations</h3>
            <p className="section-sub mb-3">
              Open Collection Workspace for the full offer grid and probability chain
            </p>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2 text-left font-medium">Borrower</th>
                <th className="px-3 py-2 text-right font-medium">EV</th>
                <th className="px-3 py-2 text-right font-medium">Opt RR</th>
                <th className="px-3 py-2 text-right font-medium">PoF</th>
              </tr>
            </thead>
            <tbody>
              {topOffers.map((b) => (
                <tr key={b.customer_code} className="border-t border-slate-100 hover:bg-slate-50/80">
                  <td className="px-3 py-2">
                    <a className="text-brand-600 underline" href={`/workspace/${b.customer_code}`}>
                      {b.legal_name || b.customer_code} ({b.customer_code})
                    </a>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatGbp(Number(b.expected_value || 0))}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {b.optimal_rr != null ? `${(Number(b.optimal_rr) * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {b.p_fulfillment != null ? `${(Number(b.p_fulfillment) * 100).toFixed(0)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </DownloadableTable>
    </div>
  );
}
