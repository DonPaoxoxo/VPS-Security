"use client";

import { Network } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";
import { api } from "@/lib/api";
import type { AapanelInstance } from "@/lib/types";

export default function AapanelPage() {
  const [instances, setInstances] = useState<AapanelInstance[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<AapanelInstance[]>("/aapanel").then(setInstances).catch(() => setError("Could not load aaPanel instances."));
  }, []);

  return (
    <div>
      <PageHeader
        title="aaPanel Monitoring"
        description="Reachability is checked independently of the agent's locally observed service status, so a firewall restriction is never confused with a stopped service."
      />

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {!instances && !error && (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-20 w-full rounded-xl" />
        </div>
      )}

      {instances && instances.length === 0 && (
        <Card>
          <EmptyState icon={Network} title="No aaPanel instances registered" />
        </Card>
      )}

      <div className="space-y-3">
        {instances?.map((i) => (
          <Card key={i.id} interactive className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <StatusDot tone={toneForStatus(i.status)} pulse={i.status === "healthy"} />
                <div>
                  <p className="font-medium text-foreground">{i.server_name ?? i.server_id}</p>
                  <p className="text-xs text-muted-foreground">
                    {i.endpoint_url}:{i.port}
                  </p>
                </div>
              </div>
              <Badge tone={toneForStatus(i.status)}>{i.status.replace("_", " ")}</Badge>
            </div>
            {i.last_status_detail && <p className="mt-3 text-xs text-muted-foreground">{i.last_status_detail}</p>}
            <p className="mt-1 text-xs text-muted-foreground">
              Last checked: {i.last_checked_at ? new Date(i.last_checked_at).toLocaleString() : "Never"}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}
