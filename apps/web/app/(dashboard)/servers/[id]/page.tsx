"use client";

import { Globe } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonStatGrid, SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import type { ServerSummary, Website } from "@/lib/types";

export default function ServerDetailPage() {
  const params = useParams<{ id: string }>();
  const [server, setServer] = useState<ServerSummary | null>(null);
  const [websites, setWebsites] = useState<Website[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState(false);
  const [revokeMessage, setRevokeMessage] = useState<string | null>(null);

  function load() {
    api
      .get<ServerSummary>(`/servers/${params.id}`)
      .then(setServer)
      .catch(() => setError("Could not load this server."));
    api
      .get<Website[]>(`/domains?server_id=${params.id}`)
      .then(setWebsites)
      .catch(() => setWebsites([]));
  }

  useEffect(load, [params.id]);

  async function handleRevoke() {
    if (!confirm("Revoke this server's agent credentials? The agent will stop being able to report in until re-enrolled.")) {
      return;
    }
    setRevoking(true);
    setRevokeMessage(null);
    try {
      await api.post(`/servers/${params.id}/agent/revoke`);
      setRevokeMessage("Agent credentials revoked.");
      load();
    } catch (err) {
      setRevokeMessage(err instanceof ApiError ? err.message : "Failed to revoke agent");
    } finally {
      setRevoking(false);
    }
  }

  if (error) {
    return <div className="rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">{error}</div>;
  }
  if (!server) {
    return (
      <div>
        <PageHeader title="Loading server…" />
        <SkeletonStatGrid count={6} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={server.name}
        description={server.hostname_or_ip}
        actions={
          server.agent_status && server.agent_status !== "never_connected" ? (
            <Button variant="destructive" onClick={handleRevoke} disabled={revoking}>
              {revoking ? "Revoking..." : "Revoke Agent"}
            </Button>
          ) : undefined
        }
      />
      {revokeMessage && <p className="mb-4 text-sm text-muted-foreground">{revokeMessage}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard title="Agent Status">
          <Badge tone={toneForStatus(server.agent_status ?? "never_connected")}>
            {server.agent_status ?? "never_connected"}
          </Badge>
        </InfoCard>
        <InfoCard title="CPU">{server.cpu_pct != null ? `${server.cpu_pct.toFixed(0)}%` : "—"}</InfoCard>
        <InfoCard title="RAM">{server.ram_pct != null ? `${server.ram_pct.toFixed(0)}%` : "—"}</InfoCard>
        <InfoCard title="Disk">{server.disk_pct != null ? `${server.disk_pct.toFixed(0)}%` : "—"}</InfoCard>
        <InfoCard title="Operating System">{server.operating_system ?? "Unknown"}</InfoCard>
        <InfoCard title="Provider">{server.provider ?? "—"}</InfoCard>
        <InfoCard title="Last Heartbeat">
          {server.last_heartbeat_at ? new Date(server.last_heartbeat_at).toLocaleString() : "Never"}
        </InfoCard>
        {server.has_aapanel && (
          <InfoCard title="aaPanel Status">
            <Badge tone={toneForStatus(server.aapanel_status ?? "unknown")}>{server.aapanel_status ?? "unknown"}</Badge>
          </InfoCard>
        )}
      </div>

      <h2 className="mb-3 mt-8 text-sm font-semibold text-foreground">Websites on this server</h2>
      {!websites && <SkeletonTable rows={3} cols={3} />}
      {websites && websites.length === 0 && (
        <TableContainer>
          <EmptyState icon={Globe} title="No websites discovered yet" />
        </TableContainer>
      )}
      {websites && websites.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>Domain</Th>
                <Th>Type</Th>
                <Th>Status</Th>
              </tr>
            </TableHead>
            <TableBody>
              {websites.map((w) => (
                <TableRow key={w.id}>
                  <Td>{w.domains.map((d) => d.hostname).join(", ") || w.document_root}</Td>
                  <Td className="text-muted-foreground">{w.website_type}</Td>
                  <Td>
                    <Badge tone={toneForStatus(w.discovery_status)}>{w.discovery_status}</Badge>
                  </Td>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </div>
  );
}

function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card interactive>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 text-lg font-medium text-foreground">{children}</CardContent>
    </Card>
  );
}
