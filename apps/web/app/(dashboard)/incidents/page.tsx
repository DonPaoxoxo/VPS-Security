"use client";

import { AlertTriangle, Clock } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { Alert, DowntimeIncident } from "@/lib/types";

export default function IncidentsPage() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [incidents, setIncidents] = useState<DowntimeIncident[] | null>(null);
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
      <PageHeader
        title="Incidents & Alerts"
        description="Active and historical alerts, plus the downtime incidents behind them."
      />

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      <h2 className="mb-3 text-sm font-semibold text-foreground">Alerts</h2>
      {!alerts && (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
        </div>
      )}
      {alerts && alerts.length === 0 && (
        <Card>
          <EmptyState icon={AlertTriangle} title="No alerts yet" />
        </Card>
      )}
      <div className="space-y-2">
        {alerts?.map((a) => (
          <Card key={a.id} className="p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <Badge tone={toneForStatus(a.severity)}>{a.severity}</Badge>
                  <p className="text-sm font-medium text-foreground">{a.title}</p>
                </div>
                {a.detail && <p className="mt-1 text-xs text-muted-foreground">{a.detail}</p>}
                <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {new Date(a.triggered_at).toLocaleString()}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
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
          </Card>
        ))}
      </div>

      <h2 className="mb-3 mt-8 text-sm font-semibold text-foreground">Downtime Incidents</h2>
      {!incidents && <Skeleton className="h-32 w-full rounded-xl" />}
      {incidents && incidents.length === 0 && (
        <TableContainer>
          <EmptyState icon={Clock} title="No downtime incidents recorded yet" />
        </TableContainer>
      )}
      {incidents && incidents.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>Target</Th>
                <Th>Started</Th>
                <Th>Resolved</Th>
                <Th>Cause</Th>
              </tr>
            </TableHead>
            <TableBody>
              {incidents.map((i) => (
                <TableRow key={i.id}>
                  <Td>
                    {i.target_type} {i.target_id.slice(0, 8)}
                  </Td>
                  <Td className="text-muted-foreground">{new Date(i.started_at).toLocaleString()}</Td>
                  <Td className="text-muted-foreground">
                    {i.resolved_at ? new Date(i.resolved_at).toLocaleString() : "Ongoing"}
                  </Td>
                  <Td className="text-muted-foreground">{i.cause.replace(/_/g, " ")}</Td>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </div>
  );
}
