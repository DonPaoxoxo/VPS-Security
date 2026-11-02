"use client";

import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { IpInvestigation } from "@/lib/types";

export default function IpInvestigationPage() {
  const [ips, setIps] = useState<IpInvestigation[] | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    api.get<IpInvestigation[]>(`/ip-investigation${query}`).then(setIps).catch(() => setError("Could not load IP data."));
  }, [search]);

  return (
    <div>
      <PageHeader
        title="IP Investigation"
        description="Approximate geolocation and ISP data based on recorded logs — not a claim of physical device identity."
      />

      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search by IP address" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {!ips && !error && <SkeletonTable rows={6} cols={7} />}

      {ips && ips.length === 0 && (
        <TableContainer>
          <EmptyState icon={Search} title="No observed IP addresses yet" />
        </TableContainer>
      )}

      {ips && ips.length > 0 && (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <Th>IP Address</Th>
                <Th>Location</Th>
                <Th>ISP / ASN</Th>
                <Th>First Seen</Th>
                <Th>Last Seen</Th>
                <Th>Login Attempts</Th>
                <Th>Security Events</Th>
              </tr>
            </TableHead>
            <TableBody>
              {ips.map((ip) => (
                <TableRow key={ip.ip_address}>
                  <Td className="font-mono">{ip.ip_address}</Td>
                  <Td className="text-muted-foreground">{[ip.city, ip.country].filter(Boolean).join(", ") || "Unknown"}</Td>
                  <Td className="text-muted-foreground">
                    {ip.isp ?? "Unknown"} {ip.asn ? `(${ip.asn})` : ""}
                  </Td>
                  <Td className="text-muted-foreground">{new Date(ip.first_seen_at).toLocaleDateString()}</Td>
                  <Td className="text-muted-foreground">{new Date(ip.last_seen_at).toLocaleString()}</Td>
                  <Td>{ip.login_attempt_count}</Td>
                  <Td>{ip.related_security_event_count}</Td>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </div>
  );
}
