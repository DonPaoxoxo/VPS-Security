"use client";

import { Plus, Search, Server as ServerIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { UsageBar } from "@/components/ui/usage-bar";
import { api } from "@/lib/api";
import type { ServerSummary } from "@/lib/types";

export default function ServersPage() {
  const [servers, setServers] = useState<ServerSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api
      .get<ServerSummary[]>("/servers")
      .then(setServers)
      .catch(() => setError("Could not load servers from the API."));
  }, []);

  const filtered = useMemo(() => {
    if (!servers) return null;
    const q = query.trim().toLowerCase();
    if (!q) return servers;
    return servers.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.hostname_or_ip.toLowerCase().includes(q) ||
        (s.provider ?? "").toLowerCase().includes(q)
    );
  }, [servers, query]);

  return (
    <div>
      <PageHeader
        title="Servers"
        description="All registered VPS instances and their agent status."
        actions={
          <Link href="/servers/new">
            <Button>
              <Plus className="h-4 w-4" />
              Add Server
            </Button>
          </Link>
        }
      />

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {servers && servers.length > 0 && (
        <div className="relative mb-4 max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name, host, or provider…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      {!servers && !error && <SkeletonTable rows={6} cols={6} />}

      {servers && servers.length === 0 && (
        <TableContainer>
          <EmptyState
            icon={ServerIcon}
            title="No servers registered yet"
            description="Add your first VPS to start monitoring resource usage, aaPanel health, and security events."
            action={
              <Link href="/servers/new">
                <Button>
                  <Plus className="h-4 w-4" />
                  Add Server
                </Button>
              </Link>
            }
          />
        </TableContainer>
      )}

      {filtered && filtered.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>Name</Th>
                <Th>Host</Th>
                <Th>Provider</Th>
                <Th>Agent</Th>
                <Th>aaPanel</Th>
                <Th>CPU</Th>
                <Th>RAM</Th>
                <Th>Disk</Th>
                <Th>Last Heartbeat</Th>
              </tr>
            </TableHead>
            <TableBody>
              {filtered.map((s) => (
                <TableRow key={s.id}>
                  <Td>
                    <Link href={`/servers/${s.id}`} className="font-medium text-foreground hover:text-accent">
                      {s.name}
                    </Link>
                  </Td>
                  <Td className="text-muted-foreground">{s.hostname_or_ip}</Td>
                  <Td className="text-muted-foreground">{s.provider ?? "—"}</Td>
                  <Td>
                    <Badge tone={toneForStatus(s.agent_status ?? "never_connected")}>
                      {s.agent_status ?? "never_connected"}
                    </Badge>
                  </Td>
                  <Td>
                    {s.has_aapanel ? (
                      <Badge tone={toneForStatus(s.aapanel_status ?? "unknown")}>{s.aapanel_status ?? "unknown"}</Badge>
                    ) : (
                      <span className="text-muted-foreground">N/A</span>
                    )}
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
                  <Td className="text-muted-foreground">
                    {s.last_heartbeat_at ? new Date(s.last_heartbeat_at).toLocaleString() : "Never"}
                  </Td>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {filtered && filtered.length === 0 && servers && servers.length > 0 && (
        <TableContainer>
          <EmptyState icon={Search} title="No servers match your search" description={`No results for "${query}".`} />
        </TableContainer>
      )}
    </div>
  );
}
