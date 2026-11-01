"use client";

import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { AapanelInstance } from "@/lib/types";

export default function AapanelPage() {
  const [instances, setInstances] = useState<AapanelInstance[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<AapanelInstance[]>("/aapanel").then(setInstances).catch(() => setError("Could not load aaPanel instances."));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold">aaPanel Monitoring</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Reachability is checked independently of the agent's locally observed service status, so a firewall
        restriction is never confused with a stopped service.
      </p>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <div className="mt-4 space-y-3">
        {instances.map((i) => (
          <div key={i.id} className="rounded-lg border border-card-border p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{i.server_name ?? i.server_id}</p>
                <p className="text-xs text-muted-foreground">
                  {i.endpoint_url}:{i.port}
                </p>
              </div>
              <Badge tone={toneForStatus(i.status)}>{i.status.replace("_", " ")}</Badge>
            </div>
            {i.last_status_detail && <p className="mt-2 text-xs text-muted-foreground">{i.last_status_detail}</p>}
            <p className="mt-1 text-xs text-muted-foreground">
              Last checked: {i.last_checked_at ? new Date(i.last_checked_at).toLocaleString() : "Never"}
            </p>
          </div>
        ))}
        {instances.length === 0 && <p className="text-sm text-muted-foreground">No aaPanel instances registered.</p>}
      </div>
    </div>
  );
}
