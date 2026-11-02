"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, ExternalLink, Globe, Search, X } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Website } from "@/lib/types";

const TABS = [
  { key: "all", label: "All Domains" },
  { key: "wordpress", label: "WordPress" },
  { key: "static", label: "Static" },
  { key: "other", label: "Other / Unknown" },
];

const PAGE_SIZE = 25;

type SortKey = "domain" | "type" | "server" | "ssl" | "status" | "last_discovered";
type SortDir = "asc" | "desc";

function primaryHostname(w: Website): string {
  return w.domains.find((d) => d.is_primary)?.hostname ?? w.domains[0]?.hostname ?? w.document_root;
}

function siteUrl(w: Website): string {
  const host = primaryHostname(w);
  const scheme = w.ssl_available ? "https" : "http";
  const port = w.configured_port;
  const defaultPort = w.ssl_available ? 443 : 80;
  const suffix = port && port !== defaultPort ? `:${port}` : "";
  return `${scheme}://${host}${suffix}`;
}

export default function DomainsPage() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("type") ?? "all";
  const [tab, setTab] = useState(initialTab);
  const [websites, setWebsites] = useState<Website[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [serverFilter, setServerFilter] = useState("all");
  const [sslFilter, setSslFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("last_discovered");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setWebsites(null);
    const query = tab === "all" ? "" : tab === "other" ? "" : `?website_type=${tab}`;
    api
      .get<Website[]>(`/domains${query}`)
      .then((data) => setWebsites(tab === "other" ? data.filter((w) => w.website_type === "other" || w.website_type === "unknown") : data))
      .catch(() => setError("Could not load domains."));
  }, [tab]);

  // Any change to the filter inputs should snap back to page 1, since the
  // previous page number may no longer exist in the narrowed result set.
  useEffect(() => {
    setPage(1);
  }, [tab, query, serverFilter, sslFilter, statusFilter, sortKey, sortDir]);

  const serverOptions = useMemo(() => {
    if (!websites) return [];
    const names = new Set(websites.map((w) => w.server_name ?? w.server_id));
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [websites]);

  const filtered = useMemo(() => {
    if (!websites) return null;
    const q = query.trim().toLowerCase();

    let rows = websites.filter((w) => {
      if (serverFilter !== "all" && (w.server_name ?? w.server_id) !== serverFilter) return false;
      if (sslFilter === "yes" && !w.ssl_available) return false;
      if (sslFilter === "no" && w.ssl_available) return false;
      if (statusFilter !== "all" && w.discovery_status !== statusFilter) return false;
      if (!q) return true;
      const haystack = [
        ...w.domains.map((d) => d.hostname),
        w.server_name ?? "",
        w.document_root,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });

    rows = [...rows].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "domain":
          cmp = primaryHostname(a).localeCompare(primaryHostname(b));
          break;
        case "type":
          cmp = a.website_type.localeCompare(b.website_type);
          break;
        case "server":
          cmp = (a.server_name ?? "").localeCompare(b.server_name ?? "");
          break;
        case "ssl":
          cmp = Number(a.ssl_available) - Number(b.ssl_available);
          break;
        case "status":
          cmp = a.discovery_status.localeCompare(b.discovery_status);
          break;
        case "last_discovered":
          cmp = new Date(a.last_discovered_at).getTime() - new Date(b.last_discovered_at).getTime();
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return rows;
  }, [websites, query, serverFilter, sslFilter, statusFilter, sortKey, sortDir]);

  const totalPages = filtered ? Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)) : 1;
  const pageStart = (page - 1) * PAGE_SIZE;
  const paged = filtered ? filtered.slice(pageStart, pageStart + PAGE_SIZE) : null;

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function SortHeader({ label, sortBy }: { label: string; sortBy: SortKey }) {
    const active = sortKey === sortBy;
    return (
      <button
        onClick={() => toggleSort(sortBy)}
        className={cn(
          "inline-flex items-center gap-1 transition-colors hover:text-foreground",
          active && "text-foreground"
        )}
      >
        {label}
        {active ? (
          sortDir === "asc" ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-40" />
        )}
      </button>
    );
  }

  const hasActiveFilters = query.trim() !== "" || serverFilter !== "all" || sslFilter !== "all" || statusFilter !== "all";

  function clearFilters() {
    setQuery("");
    setServerFilter("all");
    setSslFilter("all");
    setStatusFilter("all");
  }

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

      {websites && websites.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search domain, server, path…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={serverFilter} onChange={(e) => setServerFilter(e.target.value)}>
            <option value="all">All servers</option>
            {serverOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
          <Select value={sslFilter} onChange={(e) => setSslFilter(e.target.value)}>
            <option value="all">SSL: any</option>
            <option value="yes">SSL: enabled</option>
            <option value="no">SSL: none</option>
          </Select>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">Status: any</option>
            <option value="approved">Approved</option>
            <option value="pending_review">Pending review</option>
            <option value="excluded">Excluded</option>
          </Select>
          {hasActiveFilters && (
            <Button variant="ghost" onClick={clearFilters}>
              <X className="h-3.5 w-3.5" />
              Clear
            </Button>
          )}
        </div>
      )}

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

      {filtered && filtered.length === 0 && websites && websites.length > 0 && (
        <TableContainer>
          <EmptyState icon={Search} title="No domains match your filters" description="Try clearing search or filters." />
        </TableContainer>
      )}

      {paged && paged.length > 0 && (
        <>
          <TableContainer>
            <Table>
              <TableHead>
                <tr>
                  <Th>
                    <SortHeader label="Domain" sortBy="domain" />
                  </Th>
                  <Th>
                    <SortHeader label="Type" sortBy="type" />
                  </Th>
                  <Th>
                    <SortHeader label="Server" sortBy="server" />
                  </Th>
                  <Th>
                    <SortHeader label="SSL" sortBy="ssl" />
                  </Th>
                  <Th>
                    <SortHeader label="Status" sortBy="status" />
                  </Th>
                  <Th>
                    <SortHeader label="Last Discovered" sortBy="last_discovered" />
                  </Th>
                </tr>
              </TableHead>
              <TableBody>
                {paged.map((w) => (
                  <TableRow key={w.id}>
                    <Td>
                      <a
                        href={siteUrl(w)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group inline-flex items-center gap-1.5 font-medium text-foreground hover:text-accent"
                      >
                        {primaryHostname(w)}
                        <ExternalLink className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                      </a>
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

          <div className="mt-3 flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Showing {pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, filtered!.length)} of {filtered!.length}
            </span>
            <div className="flex items-center gap-2">
              <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                Previous
              </Button>
              <span>
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
