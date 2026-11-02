"use client";

import { Activity } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
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
  const [logs, setLogs] = useState<AuditLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<AuditLogEntry[]>("/audit-logs").then(setLogs).catch(() => setError("Could not load activity history."));
  }, []);

  return (
    <div>
      <PageHeader title="Activity History" description="Audit trail of actions taken in this dashboard." />

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {!logs && !error && <SkeletonTable rows={6} cols={4} />}

      {logs && logs.length === 0 && (
        <TableContainer>
          <EmptyState icon={Activity} title="No activity recorded yet" />
        </TableContainer>
      )}

      {logs && logs.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>Time</Th>
                <Th>Action</Th>
                <Th>Resource</Th>
                <Th>IP Address</Th>
              </tr>
            </TableHead>
            <TableBody>
              {logs.map((l) => (
                <TableRow key={l.id}>
                  <Td className="text-muted-foreground">{new Date(l.created_at).toLocaleString()}</Td>
                  <Td>{l.action}</Td>
                  <Td className="text-muted-foreground">
                    {l.resource_type ? `${l.resource_type} ${l.resource_id?.slice(0, 8) ?? ""}` : "—"}
                  </Td>
                  <Td className="font-mono text-xs">{l.ip_address ?? "—"}</Td>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </div>
  );
}
