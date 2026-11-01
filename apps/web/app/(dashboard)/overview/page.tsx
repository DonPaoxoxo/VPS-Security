"use client";

import { FileWarning, Globe, KeyRound, Network, Server, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { StatCard } from "@/components/stat-card";
import { api } from "@/lib/api";
import type { OverviewStats } from "@/lib/types";

export default function OverviewPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<OverviewStats>("/overview")
      .then(setStats)
      .catch(() => setError("Could not load overview data from the API."));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold">Overview</h1>
      <p className="mt-1 text-sm text-muted-foreground">Live status across all registered infrastructure.</p>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      {stats && (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <StatCard label="Total Servers" value={stats.total_servers} icon={Server} />
          <StatCard label="Online Servers" value={stats.online_servers} icon={Server} tone="healthy" />
          <StatCard label="Offline Servers" value={stats.offline_servers} icon={Server} tone="critical" />
          <StatCard label="Healthy aaPanel" value={stats.healthy_aapanel} icon={Network} tone="healthy" />
          <StatCard label="Unreachable aaPanel" value={stats.unreachable_aapanel} icon={Network} tone="warning" />
          <StatCard label="Total Domains" value={stats.total_domains} icon={Globe} />
          <StatCard label="WordPress Sites" value={stats.wordpress_sites} icon={Globe} />
          <StatCard label="Static Websites" value={stats.static_sites} icon={Globe} />
          <StatCard label="Other Websites" value={stats.other_sites} icon={Globe} />
          <StatCard label="Active Security Alerts" value={stats.active_security_alerts} icon={ShieldAlert} tone="warning" />
          <StatCard label="File Modification Alerts" value={stats.file_modification_alerts} icon={FileWarning} tone="warning" />
          <StatCard label="Failed SSH Attempts (24h)" value={stats.failed_ssh_attempts_24h} icon={KeyRound} tone="critical" />
        </div>
      )}

      {!stats && !error && <p className="mt-6 text-sm text-muted-foreground">Loading...</p>}
    </div>
  );
}
