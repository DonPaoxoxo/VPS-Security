"use client";

import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { IpInvestigation } from "@/lib/types";

export default function IpInvestigationPage() {
  const [ips, setIps] = useState<IpInvestigation[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    api.get<IpInvestigation[]>(`/ip-investigation${query}`).then(setIps).catch(() => setError("Could not load IP data."));
  }, [search]);

  return (
    <div>
      <h1 className="text-xl font-semibold">IP Investigation</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Approximate geolocation and ISP data based on recorded logs — not a claim of physical device identity.
      </p>

      <div className="mt-4 flex items-center gap-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input placeholder="Search by IP address" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />
      </div>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <div className="mt-4 overflow-hidden rounded-lg border border-card-border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">IP Address</th>
              <th className="px-4 py-2">Location</th>
              <th className="px-4 py-2">ISP / ASN</th>
              <th className="px-4 py-2">First Seen</th>
              <th className="px-4 py-2">Last Seen</th>
              <th className="px-4 py-2">Login Attempts</th>
              <th className="px-4 py-2">Security Events</th>
            </tr>
          </thead>
          <tbody>
            {ips.map((ip) => (
              <tr key={ip.ip_address} className="border-t border-card-border">
                <td className="px-4 py-2 font-mono">{ip.ip_address}</td>
                <td className="px-4 py-2 text-muted-foreground">{[ip.city, ip.country].filter(Boolean).join(", ") || "Unknown"}</td>
                <td className="px-4 py-2 text-muted-foreground">{ip.isp ?? "Unknown"} {ip.asn ? `(${ip.asn})` : ""}</td>
                <td className="px-4 py-2 text-muted-foreground">{new Date(ip.first_seen_at).toLocaleDateString()}</td>
                <td className="px-4 py-2 text-muted-foreground">{new Date(ip.last_seen_at).toLocaleString()}</td>
                <td className="px-4 py-2">{ip.login_attempt_count}</td>
                <td className="px-4 py-2">{ip.related_security_event_count}</td>
              </tr>
            ))}
            {ips.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                  No observed IP addresses yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
