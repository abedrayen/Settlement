"use client";

import { useEffect, useState } from "react";
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ZAxis } from "recharts";
import { apiGet, apiPost } from "@/lib/api";
import { useRole } from "@/components/AuthProvider";
import { canAccess } from "@/lib/roles";
import { PageHeader } from "@/components/ui/PageHeader";
import { ChartCard } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/LoadingState";
import { AskAgentBridge } from "@/components/ui/DownloadableTable";
import { chartTooltipStyle, CHART_COLORS } from "@/lib/chartTheme";

type FrontierPoint = { strategy_name: string; portfolio_ev: number; risk_level: string; risk_score: number };

export default function StrategyPage() {
  const { role } = useRole();
  const canRun = canAccess(role, "strategy_run");
  const [frontier, setFrontier] = useState<FrontierPoint[]>([]);
  const [simulation, setSimulation] = useState<Record<string, unknown> | null>(null);
  const [minPf, setMinPf] = useState(0.7);
  const [maxRr, setMaxRr] = useState(0.8);
  const [jobStatus, setJobStatus] = useState<string>();
  const [loading, setLoading] = useState(true);

  const runSimulation = async () => {
    if (!canRun) return;
    setJobStatus("queued");
    const res = await apiPost<{ job_id: string; status: string }>(
      `/api/frontier/jobs?min_p_fulfill=${minPf}&max_rr=${maxRr}`,
      {},
      role,
    );
    const poll = async () => {
      const job = await apiGet<{ status: string; result?: { simulation: Record<string, unknown>; frontier: FrontierPoint[] } }>(
        `/api/frontier/jobs/${res.job_id}`,
        role,
      );
      setJobStatus(job.status);
      if (job.status === "done" && job.result) {
        setFrontier(job.result.frontier || []);
        setSimulation(job.result.simulation || null);
      } else if (job.status === "running" || job.status === "queued") {
        setTimeout(poll, 800);
      }
    };
    poll();
  };

  useEffect(() => {
    apiGet<{ frontier: FrontierPoint[]; simulation: Record<string, unknown> }>(`/api/frontier?min_p_fulfill=${minPf}`, role)
      .then((d) => { setFrontier(d.frontier || []); setSimulation(d.simulation || null); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [role]);

  if (loading) return <LoadingState message="Loading economic terms simulator..." />;

  const chartData = frontier.map((f) => ({ name: f.strategy_name, risk: f.risk_score * 100, ev: f.portfolio_ev / 1_000_000 }));
  const baseline = Number(simulation?.baseline_portfolio_ev || 0);
  const constrained = Number(simulation?.constrained_portfolio_ev || 0);
  const delta = constrained - baseline;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Economic terms simulator"
        actions={
          <AskAgentBridge
            question={`What happens to total EV if we apply a P(Fulfil) >= ${minPf} floor? Show me the efficient frontier.`}
          />
        }
      />

      <div className="card p-4 grid md:grid-cols-3 gap-4 items-end">
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
          />
          <span className="font-mono text-sm text-slate-800">{(maxRr * 100).toFixed(0)}%</span>
        </label>
        <Button onClick={runSimulation} disabled={!canRun || jobStatus === "queued" || jobStatus === "running"}>
          {jobStatus === "queued" || jobStatus === "running" ? `Job: ${jobStatus}...` : "Run simulation"}
        </Button>
      </div>

      {simulation && (
        <Alert variant="info" title="Before / After EV">
          £{baseline.toLocaleString()} → £{constrained.toLocaleString()}
          <span className={delta >= 0 ? "text-emerald-700" : "text-red-700"}>
            {" "}({delta >= 0 ? "+" : ""}£{delta.toLocaleString()})
          </span>
        </Alert>
      )}

      <ChartCard title="Efficient frontier">
        <ResponsiveContainer width="100%" height={350}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="risk" name="Risk" unit="%" tick={{ fontSize: 11 }} />
            <YAxis dataKey="ev" name="EV" unit="M" tick={{ fontSize: 11 }} />
            <ZAxis range={[120, 120]} />
            <Tooltip contentStyle={chartTooltipStyle} />
            <Scatter data={chartData} fill={CHART_COLORS.primary} />
          </ScatterChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
              <th className="px-4 py-2.5 text-left font-medium">Strategy</th>
              <th className="px-4 py-2.5 text-left font-medium">EV</th>
              <th className="px-4 py-2.5 text-left font-medium">Risk</th>
            </tr>
          </thead>
          <tbody>
            {frontier.map((f) => (
              <tr key={f.strategy_name} className="border-t border-slate-100">
                <td className="px-4 py-2.5 font-medium">{f.strategy_name}</td>
                <td className="px-4 py-2.5 tabular-nums">£{f.portfolio_ev.toLocaleString()}</td>
                <td className="px-4 py-2.5">
                  <Badge variant={f.risk_level === "Low" ? "success" : f.risk_level === "Medium" ? "warning" : "danger"}>
                    {f.risk_level}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
