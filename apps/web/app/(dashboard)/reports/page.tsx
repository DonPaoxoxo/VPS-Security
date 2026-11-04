"use client";

import { Download, FileText, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import type { ServerSummary } from "@/lib/types";

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 29);

  const [servers, setServers] = useState<ServerSummary[] | null>(null);
  const [serverId, setServerId] = useState("all");
  const [startDate, setStartDate] = useState(isoDate(thirtyDaysAgo));
  const [endDate, setEndDate] = useState(isoDate(today));
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ServerSummary[]>("/servers")
      .then(setServers)
      .catch(() => setServers([]));
  }, []);

  async function downloadReport() {
    setError(null);
    if (startDate > endDate) {
      setError("Start date must not be after end date.");
      return;
    }
    setDownloading(true);
    try {
      const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
      if (serverId !== "all") params.set("server_id", serverId);
      const { blob, filename } = await api.getBlob(`/reports/pdf?${params.toString()}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename ?? `security-report-${startDate}_${endDate}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate the report.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Reports"
        description="Generate a PDF covering uptime, security events, and incidents for a date range."
      />

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Security &amp; Uptime Report</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">From</label>
              <input
                type="date"
                value={startDate}
                max={endDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="h-10 w-full rounded-md border border-card-border bg-background px-3 text-sm outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">To</label>
              <input
                type="date"
                value={endDate}
                min={startDate}
                max={isoDate(today)}
                onChange={(e) => setEndDate(e.target.value)}
                className="h-10 w-full rounded-md border border-card-border bg-background px-3 text-sm outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Server</label>
              <Select value={serverId} onChange={(e) => setServerId(e.target.value)} className="w-full">
                <option value="all">All servers</option>
                {servers?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {error && <p className="text-sm text-critical">{error}</p>}

          <Button onClick={downloadReport} disabled={downloading}>
            {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {downloading ? "Generating…" : "Download PDF"}
          </Button>

          <p className="flex items-start gap-2 pt-2 text-xs text-muted-foreground">
            <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            The report includes uptime, downtime incidents, security events, failed logins, unapproved file
            changes, and alerts for the selected period. Large result sets are capped per section with a note in
            the PDF — the dashboard always has the full detail.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
