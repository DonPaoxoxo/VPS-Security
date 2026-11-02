"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, FileText, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { FileIntegrityEvent } from "@/lib/types";

const PAGE_SIZE = 25;

type SortKey = "time" | "server" | "file" | "change" | "account" | "approved";
type SortDir = "asc" | "desc";

export default function FileIntegrityPage() {
  const [events, setEvents] = useState<FileIntegrityEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [serverFilter, setServerFilter] = useState("all");
  const [changeFilter, setChangeFilter] = useState("all");
  const [approvedFilter, setApprovedFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("time");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);

  useEffect(() => {
    api
      .get<FileIntegrityEvent[]>("/file-integrity-events")
      .then(setEvents)
      .catch(() => setError("Could not load file integrity events."));
  }, []);

  useEffect(() => {
    setPage(1);
  }, [query, serverFilter, changeFilter, approvedFilter, sortKey, sortDir]);

  const serverOptions = useMemo(() => {
    if (!events) return [];
    return Array.from(new Set(events.map((e) => e.server_name ?? e.server_id))).sort((a, b) => a.localeCompare(b));
  }, [events]);

  const changeOptions = useMemo(() => {
    if (!events) return [];
    return Array.from(new Set(events.map((e) => e.change_type))).sort((a, b) => a.localeCompare(b));
  }, [events]);

  const filtered = useMemo(() => {
    if (!events) return null;
    const q = query.trim().toLowerCase();

    let rows = events.filter((e) => {
      if (serverFilter !== "all" && (e.server_name ?? e.server_id) !== serverFilter) return false;
      if (changeFilter !== "all" && e.change_type !== changeFilter) return false;
      if (approvedFilter === "yes" && !e.is_approved_change) return false;
      if (approvedFilter === "no" && e.is_approved_change) return false;
      if (!q) return true;
      const haystack = [e.file_path, e.server_name ?? "", e.responsible_account ?? "", e.change_type].join(" ").toLowerCase();
      return haystack.includes(q);
    });

    rows = [...rows].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "time":
          cmp = new Date(a.detected_at).getTime() - new Date(b.detected_at).getTime();
          break;
        case "server":
          cmp = (a.server_name ?? "").localeCompare(b.server_name ?? "");
          break;
        case "file":
          cmp = a.file_path.localeCompare(b.file_path);
          break;
        case "change":
          cmp = a.change_type.localeCompare(b.change_type);
          break;
        case "account":
          cmp = (a.responsible_account ?? "").localeCompare(b.responsible_account ?? "");
          break;
        case "approved":
          cmp = Number(a.is_approved_change) - Number(b.is_approved_change);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return rows;
  }, [events, query, serverFilter, changeFilter, approvedFilter, sortKey, sortDir]);

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
        className={cn("inline-flex items-center gap-1 transition-colors hover:text-foreground", active && "text-foreground")}
      >
        {label}
        {active ? (
          sortDir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-40" />
        )}
      </button>
    );
  }

  const hasActiveFilters = query.trim() !== "" || serverFilter !== "all" || changeFilter !== "all" || approvedFilter !== "all";

  function clearFilters() {
    setQuery("");
    setServerFilter("all");
    setChangeFilter("all");
    setApprovedFilter("all");
  }

  return (
    <div>
      <PageHeader
        title="File Integrity"
        description={
          'Changes to monitored files. The responsible account/process shows "Unknown" when it can\'t be reliably determined — it is never guessed.'
        }
      />

      {events && events.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search file, server, account…"
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
          <Select value={changeFilter} onChange={(e) => setChangeFilter(e.target.value)}>
            <option value="all">Change: any</option>
            {changeOptions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <Select value={approvedFilter} onChange={(e) => setApprovedFilter(e.target.value)}>
            <option value="all">Approved: any</option>
            <option value="yes">Approved: yes</option>
            <option value="no">Approved: no</option>
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

      {!events && !error && <SkeletonTable rows={6} cols={6} />}

      {events && events.length === 0 && (
        <TableContainer>
          <EmptyState icon={FileText} title="No file changes recorded yet" />
        </TableContainer>
      )}

      {filtered && filtered.length === 0 && events && events.length > 0 && (
        <TableContainer>
          <EmptyState icon={Search} title="No events match your filters" description="Try clearing search or filters." />
        </TableContainer>
      )}

      {paged && paged.length > 0 && (
        <>
          <TableContainer>
            <Table>
              <TableHead>
                <tr>
                  <Th>
                    <SortHeader label="Time" sortBy="time" />
                  </Th>
                  <Th>
                    <SortHeader label="Server" sortBy="server" />
                  </Th>
                  <Th>
                    <SortHeader label="File" sortBy="file" />
                  </Th>
                  <Th>
                    <SortHeader label="Change" sortBy="change" />
                  </Th>
                  <Th>
                    <SortHeader label="Account" sortBy="account" />
                  </Th>
                  <Th>
                    <SortHeader label="Approved?" sortBy="approved" />
                  </Th>
                </tr>
              </TableHead>
              <TableBody>
                {paged.map((e) => (
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
              <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
