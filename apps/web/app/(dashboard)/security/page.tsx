"use client";

import { ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { SecurityEvent } from "@/lib/types";

export default function SecurityCenterPage() {
  const [events, setEvents] = useState<SecurityEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<SecurityEvent[]>("/security-events").then(setEvents).catch(() => setError("Could not load security events."));
  }, []);

  return (
    <div>
      <PageHeader
        title="Security Center"
        description="Events are labeled by actual evidence — not every anomaly is automatically a confirmed attack."
      />

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {!events && !error && <SkeletonTable rows={6} cols={6} />}

      {events && events.length === 0 && (
        <TableContainer>
          <EmptyState icon={ShieldAlert} title="No security events recorded yet" />
        </TableContainer>
      )}

      {events && events.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>Time</Th>
                <Th>Server</Th>
                <Th>Event</Th>
                <Th>Severity</Th>
                <Th>Source IP</Th>
                <Th>Investigation</Th>
              </tr>
            </TableHead>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.id}>
                  <Td className="text-muted-foreground">{new Date(e.occurred_at).toLocaleString()}</Td>
                  <Td>{e.server_name ?? e.server_id}</Td>
                  <Td>{e.event_type}</Td>
                  <Td>
                    <Badge tone={toneForStatus(e.severity)}>{e.severity}</Badge>
                  </Td>
                  <Td className="font-mono text-xs text-muted-foreground">{e.source_ip ?? "—"}</Td>
                  <Td>
                    <Badge tone={toneForStatus(e.investigation_status)}>{e.investigation_status}</Badge>
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
