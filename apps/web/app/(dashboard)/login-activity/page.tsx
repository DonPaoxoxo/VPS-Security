"use client";

import { KeyRound } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { LoginEvent } from "@/lib/types";

export default function LoginActivityPage() {
  const [events, setEvents] = useState<LoginEvent[] | null>(null);
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
      <PageHeader
        title="Login Activity"
        description="SSH login attempts collected by each server's agent."
        actions={
          <Button variant={onlyFailed ? "default" : "outline"} onClick={() => setOnlyFailed((v) => !v)}>
            {onlyFailed ? "Showing failed only" : "Show failed only"}
          </Button>
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
          <EmptyState icon={KeyRound} title="No login events recorded yet" />
        </TableContainer>
      )}

      {events && events.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>Time</Th>
                <Th>Server</Th>
                <Th>Account</Th>
                <Th>Source IP</Th>
                <Th>Method</Th>
                <Th>Result</Th>
              </tr>
            </TableHead>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.id}>
                  <Td className="text-muted-foreground">{new Date(e.occurred_at).toLocaleString()}</Td>
                  <Td>{e.server_name ?? e.server_id}</Td>
                  <Td>{e.account ?? "—"}</Td>
                  <Td className="font-mono text-xs">{e.source_ip ?? "—"}</Td>
                  <Td className="text-muted-foreground">{e.auth_method ?? "—"}</Td>
                  <Td>
                    <Badge tone={e.was_successful ? "healthy" : "critical"}>{e.was_successful ? "Success" : "Failed"}</Badge>
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
