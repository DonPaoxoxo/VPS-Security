"use client";

import { type LucideIcon, CornerDownLeft, Globe, Search, Server } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { NAV_SECTIONS } from "@/components/nav-sidebar";
import { useCommandPalette } from "@/lib/command-palette-context";
import { api } from "@/lib/api";
import type { ServerSummary, Website } from "@/lib/types";

interface ResultItem {
  key: string;
  group: "Pages" | "Servers" | "Websites";
  icon: LucideIcon;
  label: string;
  sublabel?: string;
  href: string;
}

const PAGE_ITEMS: ResultItem[] = NAV_SECTIONS.flatMap((section) =>
  section.items.map((item) => ({
    key: `page-${item.href}`,
    group: "Pages" as const,
    icon: item.icon,
    label: item.label,
    href: item.href,
  }))
);

export function CommandPalette() {
  const { open, setOpen } = useCommandPalette();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [servers, setServers] = useState<ServerSummary[] | null>(null);
  const [websites, setWebsites] = useState<Website[] | null>(null);
  const [loadedData, setLoadedData] = useState(false);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!open);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, setOpen]);

  useEffect(() => {
    if (open && !loadedData) {
      setLoadedData(true);
      api.get<ServerSummary[]>("/servers").then(setServers).catch(() => setServers([]));
      api.get<Website[]>("/domains").then(setWebsites).catch(() => setWebsites([]));
    }
  }, [open, loadedData]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();

    const pageResults = PAGE_ITEMS.filter((item) => !q || item.label.toLowerCase().includes(q));

    const serverResults: ResultItem[] = (servers ?? [])
      .filter((s) => !q || s.name.toLowerCase().includes(q) || s.hostname_or_ip.toLowerCase().includes(q))
      .slice(0, 8)
      .map((s) => ({
        key: `server-${s.id}`,
        group: "Servers" as const,
        icon: Server,
        label: s.name,
        sublabel: s.hostname_or_ip,
        href: `/servers/${s.id}`,
      }));

    const websiteResults: ResultItem[] = (websites ?? [])
      .filter((w) => {
        if (!q) return false; // only surface websites once the user is actually searching
        return w.domains.some((d) => d.hostname.toLowerCase().includes(q)) || w.document_root.toLowerCase().includes(q);
      })
      .slice(0, 8)
      .map((w) => ({
        key: `website-${w.id}`,
        group: "Websites" as const,
        icon: Globe,
        label: w.domains.find((d) => d.is_primary)?.hostname ?? w.domains[0]?.hostname ?? w.document_root,
        sublabel: w.server_name ?? undefined,
        href: `/servers/${w.server_id}`,
      }));

    return [...pageResults, ...serverResults, ...websiteResults];
  }, [query, servers, websites]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [results.length]);

  function navigate(item: ResultItem) {
    router.push(item.href);
    setOpen(false);
  }

  function onInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = results[selectedIndex];
      if (item) navigate(item);
    }
  }

  if (!open) return null;

  let runningIndex = -1;
  const groups: { name: string; items: ResultItem[] }[] = ["Pages", "Servers", "Websites"]
    .map((name) => ({ name, items: results.filter((r) => r.group === name) }))
    .filter((g) => g.items.length > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 px-4 pt-[15vh] backdrop-blur-sm" onClick={() => setOpen(false)}>
      <div
        className="w-full max-w-xl overflow-hidden rounded-xl border border-card-border bg-card shadow-elevated"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 border-b border-card-border px-4 py-3">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder="Search pages, servers, domains…"
            className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
          <kbd className="shrink-0 rounded border border-card-border px-1.5 py-0.5 text-[10px] text-muted-foreground">Esc</kbd>
        </div>

        <div className="scrollbar-thin max-h-80 overflow-y-auto p-2">
          {results.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">No results for &ldquo;{query}&rdquo;</p>
          )}

          {groups.map((group) => (
            <div key={group.name} className="mb-1">
              <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                {group.name}
              </p>
              {group.items.map((item) => {
                runningIndex += 1;
                const isSelected = runningIndex === selectedIndex;
                return (
                  <button
                    key={item.key}
                    onClick={() => navigate(item)}
                    onMouseEnter={() => setSelectedIndex(runningIndex)}
                    className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm transition-colors ${
                      isSelected ? "bg-accent/10 text-accent" : "text-foreground hover:bg-muted"
                    }`}
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    {item.sublabel && <span className="shrink-0 truncate text-xs text-muted-foreground">{item.sublabel}</span>}
                    {isSelected && <CornerDownLeft className="h-3 w-3 shrink-0 text-accent" />}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
