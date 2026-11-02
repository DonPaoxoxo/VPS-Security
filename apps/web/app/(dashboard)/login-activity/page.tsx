"use client";

import { KeyRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { LoginEvent } from "@/lib/types";

interface LoginEventGroup {
  key: string;
  server_name: string | null;
  account: string | null;
  source_ip: string | null;
  auth_method: string | null;
  was_successful: boolean;
  count: number;
  latest_at: string;
  earliest_at: string;
}

/** Repeated identical attempts (a brute-force burst from one IP) are the
 * common case here, and rendering each as its own row makes the table
 * unreadable at any real scale. Consecutive rows (the API already orders by
 * occurred_at desc) sharing server/account/IP/method/result collapse into
 * one row with a count and the time span they occurred over. */
function groupEvents(events: LoginEvent[]): LoginEventGroup[] {
  const groups: LoginEventGroup[] = [];
  for (const e of events) {
    const last = groups[groups.length - 1];
    const sameBucket =
      last &&
      last.server_name === e.server_name &&
      last.account === e.account &&
      last.source_ip === e.source_ip &&
      last.auth_method === e.auth_method &&
      last.was_successful === e.was_successful;
    if (sameBucket) {
      last.count += 1;
      last.earliest_at = e.occurred_at;
    } else {
      groups.push({
        key: e.id,
        server_name: e.server_name,
        account: e.account,
        source_ip: e.source_ip,
        auth_method: e.auth_method,
        was_successful: e.was_successful,
        count: 1,
        latest_at: e.occurred_at,
        earliest_at: e.occurred_at,
      });
    }
  }
  return groups;
}

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

  const groups = useMemo(() => (events ? groupEvents(events) : []), [events]);

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
              {groups.map((g) => (
                <TableRow key={g.key}>
                  <Td className="text-muted-foreground">
                    {g.count > 1 ? (
                      <span title={`${new Date(g.earliest_at).toLocaleString()} – ${new Date(g.latest_at).toLocaleString()}`}>
                        {new Date(g.latest_at).toLocaleString()}
                      </span>
                    ) : (
                      new Date(g.latest_at).toLocaleString()
                    )}
                  </Td>
                  <Td>{g.server_name ?? "—"}</Td>
                  <Td>{g.account ?? "—"}</Td>
                  <Td className="font-mono text-xs">{g.source_ip ?? "—"}</Td>
                  <Td className="text-muted-foreground">{g.auth_method ?? "—"}</Td>
                  <Td>
                    <div className="flex items-center gap-2">
                      <Badge tone={g.was_successful ? "healthy" : "critical"}>
                        {g.was_successful ? "Success" : "Failed"}
                      </Badge>
                      {g.count > 1 && (
                        <span
                          title={`${g.count} identical attempts between ${new Date(g.earliest_at).toLocaleTimeString()} and ${new Date(g.latest_at).toLocaleTimeString()}`}
                          className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
                        >
                          ×{g.count}
                        </span>
                      )}
                    </div>
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
