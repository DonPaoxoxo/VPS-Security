"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

interface AuditLogEntry {
  id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  created_at: string;
}

export default function ActivityHistoryPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<AuditLogEntry[]>("/audit-logs").then(setLogs).catch(() => setError("Could not load activity history."));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold">Activity History</h1>
      <p className="mt-1 text-sm text-muted-foreground">Audit trail of actions taken in this dashboard.</p>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <div className="mt-4 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Time</th>
              <th className="px-4 py-2">Action</th>
              <th className="px-4 py-2">Resource</th>
              <th className="px-4 py-2">IP Address</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} className="border-t border-card-border">
                <td className="px-4 py-2 text-muted-foreground">{new Date(l.created_at).toLocaleString()}</td>
                <td className="px-4 py-2">{l.action}</td>
                <td className="px-4 py-2 text-muted-foreground">
                  {l.resource_type ? `${l.resource_type} ${l.resource_id?.slice(0, 8) ?? ""}` : "—"}
                </td>
                <td className="px-4 py-2 font-mono text-xs">{l.ip_address ?? "—"}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                  No activity recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
