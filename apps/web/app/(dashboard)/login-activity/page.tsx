"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { LoginEvent } from "@/lib/types";

export default function LoginActivityPage() {
  const [events, setEvents] = useState<LoginEvent[]>([]);
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<LoginEvent[]>(`/login-events${onlyFailed ? "?only_failed=true" : ""}`)
      .then(setEvents)
      .catch(() => setError("Could not load login events."));
  }, [onlyFailed]);

  return (
    <div>
      <h1 className="text-xl font-semibold">Login Activity</h1>
      <p className="mt-1 text-sm text-muted-foreground">SSH login attempts collected by each server's agent.</p>

      <div className="mt-4">
        <Button variant={onlyFailed ? "default" : "outline"} onClick={() => setOnlyFailed((v) => !v)}>
          {onlyFailed ? "Showing failed only" : "Show failed only"}
        </Button>
      </div>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <div className="mt-4 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Time</th>
              <th className="px-4 py-2">Server</th>
              <th className="px-4 py-2">Account</th>
              <th className="px-4 py-2">Source IP</th>
              <th className="px-4 py-2">Method</th>
              <th className="px-4 py-2">Result</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-t border-card-border">
                <td className="px-4 py-2 text-muted-foreground">{new Date(e.occurred_at).toLocaleString()}</td>
                <td className="px-4 py-2">{e.server_name ?? e.server_id}</td>
                <td className="px-4 py-2">{e.account ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-xs">{e.source_ip ?? "—"}</td>
                <td className="px-4 py-2 text-muted-foreground">{e.auth_method ?? "—"}</td>
                <td className="px-4 py-2">
                  <Badge tone={e.was_successful ? "healthy" : "critical"}>{e.was_successful ? "Success" : "Failed"}</Badge>
                </td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  No login events recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
