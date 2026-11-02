"use client";

import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api";
import type { ServerSummary } from "@/lib/types";

interface MetricPoint {
  recorded_at: string;
  cpu_pct: number | null;
  ram_pct: number | null;
  disk_pct: number | null;
}

export default function PerformancePage() {
  const [servers, setServers] = useState<ServerSummary[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);

  useEffect(() => {
    api.get<ServerSummary[]>("/servers").then((data) => {
      setServers(data);
      if (data.length > 0) setSelected(data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!selected) return;
    api.get<MetricPoint[]>(`/performance/${selected}?hours=24`).then(setMetrics).catch(() => setMetrics([]));
  }, [selected]);

  const chartData = metrics.map((m) => ({
    time: new Date(m.recorded_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    cpu: m.cpu_pct,
    ram: m.ram_pct,
    disk: m.disk_pct,
  }));

  return (
    <div>
      <PageHeader title="Performance Monitoring" description="Last 24 hours of resource usage per server." />

      <select
        className="mb-6 rounded-md border border-card-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        {servers.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard title="CPU %" dataKey="cpu" data={chartData} color="hsl(var(--info))" gradientId="cpuGradient" />
        <ChartCard title="RAM %" dataKey="ram" data={chartData} color="hsl(var(--warning))" gradientId="ramGradient" />
        <ChartCard title="Disk %" dataKey="disk" data={chartData} color="hsl(var(--healthy))" gradientId="diskGradient" />
      </div>

      {chartData.length === 0 && (
        <p className="mt-6 text-sm text-muted-foreground">
          No performance history yet for this server — data appears once its agent starts sending heartbeats.
        </p>
      )}
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
