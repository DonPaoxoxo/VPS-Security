"use client";

import { AlertTriangle, ArrowDown, ArrowUp, ArrowUpDown, Clock, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Alert, DowntimeIncident } from "@/lib/types";

type IncidentSortKey = "target" | "started" | "resolved" | "cause";
type SortDir = "asc" | "desc";

export default function IncidentsPage() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [incidents, setIncidents] = useState<DowntimeIncident[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [alertQuery, setAlertQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");

  const [incidentQuery, setIncidentQuery] = useState("");
  const [sortKey, setSortKey] = useState<IncidentSortKey>("started");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

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

  const filteredAlerts = useMemo(() => {
    if (!alerts) return null;
    const q = alertQuery.trim().toLowerCase();
    return alerts.filter((a) => {
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (severityFilter !== "all" && a.severity !== severityFilter) return false;
      if (!q) return true;
      return [a.title, a.detail ?? "", a.alert_type].join(" ").toLowerCase().includes(q);
    });
  }, [alerts, alertQuery, statusFilter, severityFilter]);

  const hasAlertFilters = alertQuery.trim() !== "" || statusFilter !== "all" || severityFilter !== "all";
  function clearAlertFilters() {
    setAlertQuery("");
    setStatusFilter("all");
    setSeverityFilter("all");
  }

  function toggleSort(key: IncidentSortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function SortHeader({ label, sortBy }: { label: string; sortBy: IncidentSortKey }) {
    const active = sortKey === sortBy;
    return (
      <button
        onClick={() => toggleSort(sortBy)}
        className={cn("inline-flex items-center gap-1 transition-colors hover:text-foreground", active && "text-foreground")}
      >
        {label}
        {active ? (
          sortDir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-40" />
        )}
      </button>
    );
  }

  const filteredIncidents = useMemo(() => {
    if (!incidents) return null;
    const q = incidentQuery.trim().toLowerCase();
    let rows = incidents.filter((i) => {
      if (!q) return true;
      return [i.target_type, i.cause, i.detail ?? ""].join(" ").toLowerCase().includes(q);
    });
    rows = [...rows].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "target":
          cmp = a.target_type.localeCompare(b.target_type);
          break;
        case "started":
          cmp = new Date(a.started_at).getTime() - new Date(b.started_at).getTime();
          break;
        case "resolved":
          cmp = (a.resolved_at ? new Date(a.resolved_at).getTime() : Infinity) - (b.resolved_at ? new Date(b.resolved_at).getTime() : Infinity);
          break;
        case "cause":
          cmp = a.cause.localeCompare(b.cause);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [incidents, incidentQuery, sortKey, sortDir]);

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

      {alerts && alerts.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search alerts…"
              value={alertQuery}
              onChange={(e) => setAlertQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">Status: any</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
          </Select>
          <Select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
            <option value="all">Severity: any</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </Select>
          {hasAlertFilters && (
            <Button variant="ghost" onClick={clearAlertFilters}>
              <X className="h-3.5 w-3.5" />
              Clear
            </Button>
          )}
        </div>
      )}

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
      {filteredAlerts && filteredAlerts.length === 0 && alerts && alerts.length > 0 && (
        <Card>
          <EmptyState icon={Search} title="No alerts match your filters" description="Try clearing search or filters." />
        </Card>
      )}
      <div className="space-y-2">
        {filteredAlerts?.map((a) => (
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

      {incidents && incidents.length > 0 && (
        <div className="relative mb-4 max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search incidents…"
            value={incidentQuery}
            onChange={(e) => setIncidentQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      {!incidents && <Skeleton className="h-32 w-full rounded-xl" />}
      {incidents && incidents.length === 0 && (
        <TableContainer>
          <EmptyState icon={Clock} title="No downtime incidents recorded yet" />
        </TableContainer>
      )}
      {filteredIncidents && filteredIncidents.length === 0 && incidents && incidents.length > 0 && (
        <TableContainer>
          <EmptyState icon={Search} title="No incidents match your search" />
        </TableContainer>
      )}
      {filteredIncidents && filteredIncidents.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>
                  <SortHeader label="Target" sortBy="target" />
                </Th>
                <Th>
                  <SortHeader label="Started" sortBy="started" />
                </Th>
                <Th>
                  <SortHeader label="Resolved" sortBy="resolved" />
                </Th>
                <Th>
                  <SortHeader label="Cause" sortBy="cause" />
                </Th>
              </tr>
            </TableHead>
            <TableBody>
              {filteredIncidents.map((i) => (
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
