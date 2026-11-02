"use client";

import { Gauge } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge, toneForStatus } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { ServerSummary } from "@/lib/types";

interface MetricPoint {
  recorded_at: string;
  cpu_pct: number | null;
  ram_pct: number | null;
  disk_pct: number | null;
}

export default function PerformancePage() {
  const [servers, setServers] = useState<ServerSummary[] | null>(null);
  const [metricsByServer, setMetricsByServer] = useState<Record<string, MetricPoint[]>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ServerSummary[]>("/servers")
      .then(async (data) => {
        setServers(data);
        const entries = await Promise.all(
          data.map(async (s) => {
            try {
              const points = await api.get<MetricPoint[]>(`/performance/${s.id}?hours=24`);
              return [s.id, points] as const;
            } catch {
              return [s.id, []] as const;
            }
          })
        );
        setMetricsByServer(Object.fromEntries(entries));
      })
      .catch(() => setError("Could not load servers from the API."));
  }, []);

  return (
    <div>
      <PageHeader title="Performance Monitoring" description="Last 24 hours of resource usage across every server." />

      {error && (
        <div className="mb-6 rounded-xl border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
          {error}
        </div>
      )}

      {!servers && !error && (
        <div className="space-y-6">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i}>
              <Skeleton className="mb-3 h-4 w-40" />
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <Skeleton className="h-56 w-full rounded-xl" />
                <Skeleton className="h-56 w-full rounded-xl" />
                <Skeleton className="h-56 w-full rounded-xl" />
              </div>
            </div>
          ))}
        </div>
      )}

      {servers && servers.length === 0 && (
        <Card>
          <EmptyState icon={Gauge} title="No servers registered yet" description="Add a server to start seeing resource usage history here." />
        </Card>
      )}

      <div className="space-y-8">
        {servers?.map((s) => {
          const metrics = metricsByServer[s.id];
          const chartData = (metrics ?? []).map((m) => ({
            time: new Date(m.recorded_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            cpu: m.cpu_pct,
            ram: m.ram_pct,
            disk: m.disk_pct,
          }));

          return (
            <div key={s.id}>
              <div className="mb-3 flex items-center gap-2.5">
                <Link href={`/servers/${s.id}`} className="text-sm font-semibold text-foreground hover:text-accent">
                  {s.name}
                </Link>
                <Badge tone={toneForStatus(s.agent_status ?? "never_connected")}>
                  {s.agent_status ?? "never_connected"}
                </Badge>
                <span className="text-xs text-muted-foreground">{s.hostname_or_ip}</span>
              </div>

              {metrics === undefined && (
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                  <Skeleton className="h-56 w-full rounded-xl" />
                  <Skeleton className="h-56 w-full rounded-xl" />
                  <Skeleton className="h-56 w-full rounded-xl" />
                </div>
              )}

              {metrics !== undefined && chartData.length === 0 && (
                <Card>
                  <EmptyState
                    icon={Gauge}
                    title="No performance history yet"
                    description="Data appears once this server's agent starts sending heartbeats."
                  />
                </Card>
              )}

              {chartData.length > 0 && (
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                  <ChartCard title="CPU %" dataKey="cpu" data={chartData} color="hsl(var(--info))" gradientId={`cpuGradient-${s.id}`} />
                  <ChartCard title="RAM %" dataKey="ram" data={chartData} color="hsl(var(--warning))" gradientId={`ramGradient-${s.id}`} />
                  <ChartCard title="Disk %" dataKey="disk" data={chartData} color="hsl(var(--healthy))" gradientId={`diskGradient-${s.id}`} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ChartCard({
  title,
  dataKey,
  data,
  color,
  gradientId,
}: {
  title: string;
  dataKey: string;
  data: Array<Record<string, string | number | null>>;
  color: string;
  gradientId: string;
}) {
  return (
    <Card interactive>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.35} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--card-border))" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
              domain={[0, 100]}
              axisLine={false}
              tickLine={false}
              width={28}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--card-border))",
                borderRadius: "0.5rem",
                fontSize: "0.75rem",
              }}
            />
            <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} fill={`url(#${gradientId})`} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
