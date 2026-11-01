"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { FileIntegrityEvent } from "@/lib/types";

export default function FileIntegrityPage() {
  const [events, setEvents] = useState<FileIntegrityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<FileIntegrityEvent[]>("/file-integrity-events").then(setEvents).catch(() => setError("Could not load file integrity events."));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold">File Integrity</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Changes to monitored files. The responsible account/process shows "Unknown" when it can't be reliably
        determined — it is never guessed.
      </p>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <div className="mt-4 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Time</th>
              <th className="px-4 py-2">Server</th>
              <th className="px-4 py-2">File</th>
              <th className="px-4 py-2">Change</th>
              <th className="px-4 py-2">Account</th>
              <th className="px-4 py-2">Approved?</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-t border-card-border">
                <td className="px-4 py-2 text-muted-foreground">{new Date(e.detected_at).toLocaleString()}</td>
                <td className="px-4 py-2">{e.server_name ?? e.server_id}</td>
                <td className="px-4 py-2 font-mono text-xs">{e.file_path}</td>
                <td className="px-4 py-2">{e.change_type}</td>
                <td className="px-4 py-2 text-muted-foreground">{e.responsible_account ?? "Unknown"}</td>
                <td className="px-4 py-2">
                  <Badge tone={e.is_approved_change ? "healthy" : "warning"}>{e.is_approved_change ? "Yes" : "No"}</Badge>
                </td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  No file changes recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
