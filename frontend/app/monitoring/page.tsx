"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/LoadingState";

type Metric = {
  model_name: string;
  metric_name: string;
  metric_value: number;
  baseline_value: number;
  alert_flag: boolean;
  drift: number;
};

export default function MonitoringPage() {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [alerts, setAlerts] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<{ metrics: Metric[]; alerts: Metric[] }>("/api/monitoring")
      .then((d) => { setMetrics(d.metrics || []); setAlerts(d.alerts || []); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState message="Loading model health..." />;

  return (
    <div className="page-container">
      <PageHeader
        title="Model Health"
        badge={alerts.length > 0 ? <Badge variant="danger">{alerts.length} alerts</Badge> : <Badge variant="success">Healthy</Badge>}
      />

      {alerts.length > 0 && (
        <Alert variant="danger" title={`${alerts.length} alert(s) require attention`}>
          {alerts.map((a, i) => (
            <span key={i}>{a.model_name} {a.metric_name}: {a.metric_value} (baseline {a.baseline_value}){i < alerts.length - 1 ? " · " : ""}</span>
          ))}
        </Alert>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50/80 text-slate-500 text-xs uppercase tracking-wide">
              <th className="px-4 py-3 text-left">Model</th>
              <th className="px-4 py-3 text-left">Metric</th>
              <th className="px-4 py-3 text-left">Value</th>
              <th className="px-4 py-3 text-left">Baseline</th>
              <th className="px-4 py-3 text-left">Drift</th>
              <th className="px-4 py-3 text-left">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {metrics.map((m, i) => (
              <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3 font-medium">{m.model_name}</td>
                <td className="px-4 py-3 text-slate-600">{m.metric_name}</td>
                <td className="px-4 py-3">{m.metric_value}</td>
                <td className="px-4 py-3 text-slate-500">{m.baseline_value}</td>
                <td className={`px-4 py-3 font-medium ${m.drift > 0 ? "text-amber-600" : "text-emerald-600"}`}>
                  {m.drift > 0 ? "+" : ""}{m.drift}
                </td>
                <td className="px-4 py-3">
                  <Badge variant={m.alert_flag ? "danger" : "success"}>{m.alert_flag ? "ALERT" : "OK"}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
