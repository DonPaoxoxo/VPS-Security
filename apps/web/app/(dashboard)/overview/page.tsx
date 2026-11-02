"use client";

import {
  AlertTriangle,
  CheckCircle2,
  FileWarning,
  Globe,
  KeyRound,
  Network,
  Server,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { StatCard } from "@/components/stat-card";
import { Badge, toneForStatus } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonStatGrid, SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { UsageBar } from "@/components/ui/usage-bar";
import { api } from "@/lib/api";
import type { OverviewStats, ServerSummary } from "@/lib/types";

export default function OverviewPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [servers, setServers] = useState<ServerSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<OverviewStats>("/overview")
      .then(setStats)
      .catch(() => setError("Could not load overview data from the API."));
    api
      .get<ServerSummary[]>("/servers")
      .then(setServers)
      .catch(() => setServers([]));
  }, []);

  const issueCount = stats
    ? stats.offline_servers + stats.unreachable_aapanel + stats.active_security_alerts
    : 0;
  const allHealthy = stats && issueCount === 0;

  return (
    <div>
      <PageHeader title="Overview" description="Live status across all registered infrastructure." />

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {stats && (
        <div
          className={`mb-6 flex items-center gap-3 rounded-xl border px-4 py-3.5 ${
            allHealthy ? "border-healthy/30 bg-healthy/10" : "border-warning/30 bg-warning/10"
          }`}
        >
          {allHealthy ? (
            <CheckCircle2 className="h-5 w-5 shrink-0 text-healthy" />
          ) : (
            <AlertTriangle className="h-5 w-5 shrink-0 text-warning" />
          )}
          <p className={`text-sm font-medium ${allHealthy ? "text-healthy" : "text-warning"}`}>
            {allHealthy
              ? "All systems operational"
              : `${issueCount} item${issueCount === 1 ? "" : "s"} need attention across your fleet`}
          </p>
        </div>
      )}

      {!stats && !error && <SkeletonStatGrid count={8} />}

      {stats && (
        <div className="space-y-6">
          <StatGroup title="Infrastructure">
            <StatCard label="Total Servers" value={stats.total_servers} icon={Server} />
            <StatCard label="Online Servers" value={stats.online_servers} icon={Server} tone="healthy" />
            <StatCard label="Offline Servers" value={stats.offline_servers} icon={Server} tone="critical" />
            <StatCard label="Healthy aaPanel" value={stats.healthy_aapanel} icon={Network} tone="healthy" />
            <StatCard label="Unreachable aaPanel" value={stats.unreachable_aapanel} icon={Network} tone="warning" />
          </StatGroup>

          <StatGroup title="Websites">
            <StatCard label="Total Domains" value={stats.total_domains} icon={Globe} />
            <StatCard label="WordPress Sites" value={stats.wordpress_sites} icon={Globe} tone="info" />
            <StatCard label="Static Websites" value={stats.static_sites} icon={Globe} tone="info" />
            <StatCard label="Other Websites" value={stats.other_sites} icon={Globe} />
          </StatGroup>

          <StatGroup title="Security">
            <StatCard label="Active Security Alerts" value={stats.active_security_alerts} icon={ShieldAlert} tone="warning" />
            <StatCard label="File Modification Alerts" value={stats.file_modification_alerts} icon={FileWarning} tone="warning" />
            <StatCard label="Failed SSH Attempts (24h)" value={stats.failed_ssh_attempts_24h} icon={KeyRound} tone="critical" />
          </StatGroup>
        </div>
      )}

      <div className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Fleet at a glance</h2>
          <Link href="/servers" className="text-xs font-medium text-accent hover:underline">
            View all servers
          </Link>
        </div>

        {!servers && <SkeletonTable rows={4} cols={5} />}

        {servers && servers.length === 0 && (
          <TableContainer>
            <EmptyState
              icon={Server}
              title="No servers registered yet"
              description="Add your first server to start seeing live resource usage here."
            />
          </TableContainer>
        )}

        {servers && servers.length > 0 && (
          <TableContainer>
            <Table>
              <TableHead>
                <tr>
                  <Th>Server</Th>
                  <Th>Agent</Th>
                  <Th>CPU</Th>
                  <Th>RAM</Th>
                  <Th>Disk</Th>
                </tr>
              </TableHead>
              <TableBody>
                {servers.slice(0, 8).map((s) => (
                  <TableRow key={s.id} clickable>
                    <Td>
                      <Link href={`/servers/${s.id}`} className="font-medium text-foreground hover:text-accent">
                        {s.name}
                      </Link>
                    </Td>
                    <Td>
                      <Badge tone={toneForStatus(s.agent_status ?? "never_connected")}>
                        {s.agent_status ?? "never_connected"}
                      </Badge>
                    </Td>
                    <Td>
                      <UsageBar value={s.cpu_pct} />
                    </Td>
                    <Td>
                      <UsageBar value={s.ram_pct} />
                    </Td>
                    <Td>
                      <UsageBar value={s.disk_pct} />
                    </Td>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </div>
    </div>
  );
}

function StatGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold text-foreground">{title}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{children}</div>
    </div>
  );
}
