"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { ServerSummary, Website } from "@/lib/types";

export default function ServerDetailPage() {
  const params = useParams<{ id: string }>();
  const [server, setServer] = useState<ServerSummary | null>(null);
  const [websites, setWebsites] = useState<Website[]>([]);
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
      .catch(() => undefined);
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

  if (error) return <p className="text-sm text-critical">{error}</p>;
  if (!server) return <p className="text-sm text-muted-foreground">Loading...</p>;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{server.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{server.hostname_or_ip}</p>
        </div>
        {server.agent_status && server.agent_status !== "never_connected" && (
          <Button variant="destructive" onClick={handleRevoke} disabled={revoking}>
            {revoking ? "Revoking..." : "Revoke Agent"}
          </Button>
        )}
      </div>
      {revokeMessage && <p className="mt-2 text-sm text-muted-foreground">{revokeMessage}</p>}

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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

      <h2 className="mt-8 text-sm font-medium text-muted-foreground">Websites on this server</h2>
      <div className="mt-2 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Domain</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {websites.map((w) => (
              <tr key={w.id} className="border-t border-card-border">
                <td className="px-4 py-2">{w.domains.map((d) => d.hostname).join(", ") || w.document_root}</td>
                <td className="px-4 py-2 text-muted-foreground">{w.website_type}</td>
                <td className="px-4 py-2">
                  <Badge tone={toneForStatus(w.discovery_status)}>{w.discovery_status}</Badge>
                </td>
              </tr>
            ))}
            {websites.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-muted-foreground">
                  No websites discovered yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 text-lg font-medium">{children}</CardContent>
    </Card>
  );
}
