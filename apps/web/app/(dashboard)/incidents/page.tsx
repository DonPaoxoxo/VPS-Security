"use client";

import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Alert, DowntimeIncident } from "@/lib/types";

export default function IncidentsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [incidents, setIncidents] = useState<DowntimeIncident[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [a, i] = await Promise.all([api.get<Alert[]>("/alerts"), api.get<DowntimeIncident[]>("/incidents")]);
      setAlerts(a);
      setIncidents(i);
    } catch {
      setError("Could not load alerts/incidents.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function acknowledge(id: string) {
    await api.post(`/alerts/${id}/acknowledge`);
    load();
  }

  async function resolve(id: string) {
    await api.post(`/alerts/${id}/resolve`);
    load();
  }

  return (
    <div>
      <h1 className="text-xl font-semibold">Incidents & Alerts</h1>
      <p className="mt-1 text-sm text-muted-foreground">Active and historical alerts, plus the downtime incidents behind them.</p>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <h2 className="mt-6 text-sm font-medium text-muted-foreground">Alerts</h2>
      <div className="mt-2 space-y-2">
        {alerts.map((a) => (
          <div key={a.id} className="flex items-center justify-between rounded-lg border border-card-border p-3">
            <div>
              <div className="flex items-center gap-2">
                <Badge tone={toneForStatus(a.severity)}>{a.severity}</Badge>
                <p className="text-sm font-medium">{a.title}</p>
              </div>
              {a.detail && <p className="mt-1 text-xs text-muted-foreground">{a.detail}</p>}
              <p className="text-xs text-muted-foreground">{new Date(a.triggered_at).toLocaleString()}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={toneForStatus(a.status)}>{a.status}</Badge>
              {a.status === "open" && (
                <Button variant="outline" onClick={() => acknowledge(a.id)}>
                  Acknowledge
                </Button>
              )}
              {a.status !== "resolved" && (
                <Button variant="outline" onClick={() => resolve(a.id)}>
                  Resolve
                </Button>
              )}
            </div>
          </div>
        ))}
        {alerts.length === 0 && <p className="text-sm text-muted-foreground">No alerts yet.</p>}
      </div>

      <h2 className="mt-8 text-sm font-medium text-muted-foreground">Downtime Incidents</h2>
      <div className="mt-2 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Target</th>
              <th className="px-4 py-2">Started</th>
              <th className="px-4 py-2">Resolved</th>
              <th className="px-4 py-2">Cause</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((i) => (
              <tr key={i.id} className="border-t border-card-border">
                <td className="px-4 py-2">
                  {i.target_type} {i.target_id.slice(0, 8)}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{new Date(i.started_at).toLocaleString()}</td>
                <td className="px-4 py-2 text-muted-foreground">
                  {i.resolved_at ? new Date(i.resolved_at).toLocaleString() : "Ongoing"}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{i.cause.replace(/_/g, " ")}</td>
              </tr>
            ))}
            {incidents.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                  No downtime incidents recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
