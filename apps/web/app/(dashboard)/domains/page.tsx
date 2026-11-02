"use client";

import { Globe } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { Website } from "@/lib/types";

const TABS = [
  { key: "all", label: "All Domains" },
  { key: "wordpress", label: "WordPress" },
  { key: "static", label: "Static" },
  { key: "other", label: "Other / Unknown" },
];

export default function DomainsPage() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("type") ?? "all";
  const [tab, setTab] = useState(initialTab);
  const [websites, setWebsites] = useState<Website[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setWebsites(null);
    const query = tab === "all" ? "" : tab === "other" ? "" : `?website_type=${tab}`;
    api
      .get<Website[]>(`/domains${query}`)
      .then((data) => setWebsites(tab === "other" ? data.filter((w) => w.website_type === "other" || w.website_type === "unknown") : data))
      .catch(() => setError("Could not load domains."));
  }, [tab]);

  return (
    <div>
      <PageHeader title="Domain Inventory" description="Every discovered hostname, its classification, and monitoring status." />

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <Button key={t.key} variant={tab === t.key ? "default" : "outline"} onClick={() => setTab(t.key)}>
            {t.label}
          </Button>
        ))}
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {!websites && !error && <SkeletonTable rows={6} cols={6} />}

      {websites && websites.length === 0 && (
        <TableContainer>
          <EmptyState icon={Globe} title="No domains found for this filter" />
        </TableContainer>
      )}

      {websites && websites.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>Domain</Th>
                <Th>Type</Th>
                <Th>Server</Th>
                <Th>SSL</Th>
                <Th>Status</Th>
                <Th>Last Discovered</Th>
              </tr>
            </TableHead>
            <TableBody>
              {websites.map((w) => (
                <TableRow key={w.id}>
                  <Td>
                    <div className="font-medium text-foreground">
                      {w.domains.find((d) => d.is_primary)?.hostname ?? w.domains[0]?.hostname ?? w.document_root}
                    </div>
                    {w.domains.length > 1 && (
                      <div className="text-xs text-muted-foreground">+{w.domains.length - 1} alias(es)</div>
                    )}
                  </Td>
                  <Td className="text-muted-foreground">
                    {w.website_type} ({Math.round(w.classification_confidence * 100)}%)
                  </Td>
                  <Td className="text-muted-foreground">{w.server_name ?? w.server_id}</Td>
                  <Td>
                    <Badge tone={w.ssl_available ? "healthy" : "muted"}>{w.ssl_available ? "Yes" : "No"}</Badge>
                  </Td>
                  <Td>
                    <Badge tone={toneForStatus(w.discovery_status)}>{w.discovery_status}</Badge>
                  </Td>
                  <Td className="text-muted-foreground">{new Date(w.last_discovered_at).toLocaleString()}</Td>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </div>
  );
}
