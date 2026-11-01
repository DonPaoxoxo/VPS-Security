"use client";

import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { SecurityEvent } from "@/lib/types";

export default function SecurityCenterPage() {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<SecurityEvent[]>("/security-events").then(setEvents).catch(() => setError("Could not load security events."));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold">Security Center</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Events are labeled by actual evidence — not every anomaly is automatically a confirmed attack.
      </p>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <div className="mt-4 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Time</th>
              <th className="px-4 py-2">Server</th>
              <th className="px-4 py-2">Event</th>
              <th className="px-4 py-2">Severity</th>
              <th className="px-4 py-2">Source IP</th>
              <th className="px-4 py-2">Investigation</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-t border-card-border">
                <td className="px-4 py-2 text-muted-foreground">{new Date(e.occurred_at).toLocaleString()}</td>
                <td className="px-4 py-2">{e.server_name ?? e.server_id}</td>
                <td className="px-4 py-2">{e.event_type}</td>
                <td className="px-4 py-2">
                  <Badge tone={toneForStatus(e.severity)}>{e.severity}</Badge>
                </td>
                <td className="px-4 py-2 text-muted-foreground">{e.source_ip ?? "—"}</td>
                <td className="px-4 py-2">
                  <Badge tone={toneForStatus(e.investigation_status)}>{e.investigation_status}</Badge>
                </td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  No security events recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
