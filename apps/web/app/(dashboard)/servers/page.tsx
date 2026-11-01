"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ServerSummary } from "@/lib/types";

export default function ServersPage() {
  const [servers, setServers] = useState<ServerSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ServerSummary[]>("/servers")
      .then(setServers)
      .catch(() => setError("Could not load servers from the API."));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Servers</h1>
          <p className="mt-1 text-sm text-muted-foreground">All registered VPS instances and their agent status.</p>
        </div>
        <Link href="/servers/new">
          <Button>
            <Plus className="h-4 w-4" />
            Add Server
          </Button>
        </Link>
      </div>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <div className="mt-6 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Host</th>
              <th className="px-4 py-2">Provider</th>
              <th className="px-4 py-2">Agent</th>
              <th className="px-4 py-2">aaPanel</th>
              <th className="px-4 py-2">Last Heartbeat</th>
            </tr>
          </thead>
          <tbody>
            {servers?.map((s) => (
              <tr key={s.id} className="border-t border-card-border hover:bg-muted/50">
                <td className="px-4 py-2">
                  <Link href={`/servers/${s.id}`} className="font-medium hover:underline">
                    {s.name}
                  </Link>
                </td>
                <td className="px-4 py-2 text-muted-foreground">{s.hostname_or_ip}</td>
                <td className="px-4 py-2 text-muted-foreground">{s.provider ?? "—"}</td>
                <td className="px-4 py-2">
                  <Badge tone={toneForStatus(s.agent_status ?? "never_connected")}>
                    {s.agent_status ?? "never_connected"}
                  </Badge>
                </td>
                <td className="px-4 py-2">
                  {s.has_aapanel ? (
                    <Badge tone={toneForStatus(s.aapanel_status ?? "unknown")}>{s.aapanel_status ?? "unknown"}</Badge>
                  ) : (
                    <span className="text-muted-foreground">N/A</span>
                  )}
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {s.last_heartbeat_at ? new Date(s.last_heartbeat_at).toLocaleString() : "Never"}
                </td>
              </tr>
            ))}
            {servers && servers.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  No servers registered yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
