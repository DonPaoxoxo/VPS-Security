"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  const [websites, setWebsites] = useState<Website[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const query = tab === "all" ? "" : tab === "other" ? "" : `?website_type=${tab}`;
    api
      .get<Website[]>(`/domains${query}`)
      .then((data) => setWebsites(tab === "other" ? data.filter((w) => w.website_type === "other" || w.website_type === "unknown") : data))
      .catch(() => setError("Could not load domains."))
      .finally(() => setLoading(false));
  }, [tab]);

  return (
    <div>
      <h1 className="text-xl font-semibold">Domain Inventory</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Every discovered hostname, its classification, and monitoring status.
      </p>

      <div className="mt-4 flex gap-2">
        {TABS.map((t) => (
          <Button key={t.key} variant={tab === t.key ? "default" : "outline"} onClick={() => setTab(t.key)}>
            {t.label}
          </Button>
        ))}
      </div>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <div className="mt-4 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Domain</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Server</th>
              <th className="px-4 py-2">SSL</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Last Discovered</th>
            </tr>
          </thead>
          <tbody>
            {websites.map((w) => (
              <tr key={w.id} className="border-t border-card-border hover:bg-muted/50">
                <td className="px-4 py-2">
                  <div className="font-medium">{w.domains.find((d) => d.is_primary)?.hostname ?? w.domains[0]?.hostname ?? w.document_root}</div>
                  {w.domains.length > 1 && (
                    <div className="text-xs text-muted-foreground">+{w.domains.length - 1} alias(es)</div>
                  )}
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {w.website_type} ({Math.round(w.classification_confidence * 100)}%)
                </td>
                <td className="px-4 py-2 text-muted-foreground">{w.server_name ?? w.server_id}</td>
                <td className="px-4 py-2">
                  <Badge tone={w.ssl_available ? "healthy" : "muted"}>{w.ssl_available ? "Yes" : "No"}</Badge>
                </td>
                <td className="px-4 py-2">
                  <Badge tone={toneForStatus(w.discovery_status)}>{w.discovery_status}</Badge>
                </td>
                <td className="px-4 py-2 text-muted-foreground">{new Date(w.last_discovered_at).toLocaleString()}</td>
              </tr>
            ))}
            {!loading && websites.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  No domains found for this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
