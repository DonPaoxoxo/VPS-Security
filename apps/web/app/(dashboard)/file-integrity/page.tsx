"use client";

import { FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { FileIntegrityEvent } from "@/lib/types";

export default function FileIntegrityPage() {
  const [events, setEvents] = useState<FileIntegrityEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<FileIntegrityEvent[]>("/file-integrity-events")
      .then(setEvents)
      .catch(() => setError("Could not load file integrity events."));
  }, []);

  return (
    <div>
      <PageHeader
        title="File Integrity"
        description={
          'Changes to monitored files. The responsible account/process shows "Unknown" when it can\'t be reliably determined — it is never guessed.'
        }
      />

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {!events && !error && <SkeletonTable rows={6} cols={6} />}

      {events && events.length === 0 && (
        <TableContainer>
          <EmptyState icon={FileText} title="No file changes recorded yet" />
        </TableContainer>
      )}

      {events && events.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>Time</Th>
                <Th>Server</Th>
                <Th>File</Th>
                <Th>Change</Th>
                <Th>Account</Th>
                <Th>Approved?</Th>
              </tr>
            </TableHead>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.id}>
                  <Td className="text-muted-foreground">{new Date(e.detected_at).toLocaleString()}</Td>
                  <Td>{e.server_name ?? e.server_id}</Td>
                  <Td className="font-mono text-xs">{e.file_path}</Td>
                  <Td>{e.change_type}</Td>
                  <Td className="text-muted-foreground">{e.responsible_account ?? "Unknown"}</Td>
                  <Td>
                    <Badge tone={e.is_approved_change ? "healthy" : "warning"}>{e.is_approved_change ? "Yes" : "No"}</Badge>
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
