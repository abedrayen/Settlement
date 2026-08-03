"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";
import { useRole } from "@/components/AuthProvider";
import { canAccess } from "@/lib/roles";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/LoadingState";

export default function SettingsPage() {
  const { role } = useRole();
  const [freshness, setFreshness] = useState<{ sources: Array<{ name: string; cadence: string; last_refresh: string; stale: boolean }> } | null>(null);
  const [models, setModels] = useState<Array<{ version: string; retrain_date: string; active: boolean; components: Record<string, string> }>>([]);
  const [guardrails, setGuardrails] = useState({ rr_min: 0.2, rr_max: 0.8, flags: {} as Record<string, boolean> });
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([
      apiGet<typeof freshness>("/api/settings/freshness", role),
      canAccess(role, "settings_read") ? apiGet<typeof models>("/api/settings/models", role) : Promise.resolve([]),
      canAccess(role, "settings_read") ? apiGet<typeof guardrails>("/api/settings/guardrails", role) : Promise.resolve(null),
    ])
      .then(([f, m, g]) => {
        setFreshness(f);
        setModels(m || []);
        if (g) setGuardrails(g);
      })
      .finally(() => setLoading(false));
  }, [role]);

  const saveGuardrails = async () => {
    await apiPut("/api/settings/guardrails", guardrails, role);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (loading) return <LoadingState message="Loading settings..." />;
  if (!canAccess(role, "settings_read")) {
    return <p className="text-slate-600">Settings are available to Admin only.</p>;
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" />

      <Card>
        <h3 className="section-title mb-3">Data source status</h3>
        <div className="space-y-2">
          {freshness?.sources.map((s) => (
            <div key={s.name} className="flex items-center justify-between text-sm border-b border-slate-100 py-2">
              <span>{s.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-slate-500">{s.cadence} · {new Date(s.last_refresh).toLocaleDateString()}</span>
                {s.stale ? <Badge variant="warning">Stale</Badge> : <Badge variant="success">OK</Badge>}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <h3 className="font-semibold mb-3">Model Version History</h3>
        {models.map((m) => (
          <div key={m.version} className="flex items-center justify-between py-2 border-b border-slate-100 text-sm">
            <div>
              <span className="font-medium">{m.version}</span>
              <span className="text-slate-500 ml-2">Retrained {m.retrain_date}</span>
            </div>
            {m.active ? <Badge variant="success">Active</Badge> : <Badge variant="info">Archived</Badge>}
          </div>
        ))}
      </Card>

      {canAccess(role, "settings_write") && (
        <Card>
          <h3 className="font-semibold mb-3">Guardrail Configuration</h3>
          <div className="grid md:grid-cols-2 gap-4 text-sm">
            <label>RR Min (%)
              <input type="number" value={guardrails.rr_min * 100} onChange={(e) => setGuardrails({ ...guardrails, rr_min: Number(e.target.value) / 100 })} className="input-field mt-1" />
            </label>
            <label>RR Max (%)
              <input type="number" value={guardrails.rr_max * 100} onChange={(e) => setGuardrails({ ...guardrails, rr_max: Number(e.target.value) / 100 })} className="input-field mt-1" />
            </label>
          </div>
          <Button className="mt-4" onClick={saveGuardrails}>{saved ? "Saved" : "Save guardrail rules"}</Button>
        </Card>
      )}
    </div>
  );
}
