"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
      <h1 className="text-xl font-semibold">Performance Monitoring</h1>
      <p className="mt-1 text-sm text-muted-foreground">Last 24 hours of resource usage per server.</p>

      <select
        className="mt-4 rounded-md border border-card-border bg-background px-3 py-2 text-sm"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        {servers.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard title="CPU %" dataKey="cpu" data={chartData} color="hsl(var(--info))" />
        <ChartCard title="RAM %" dataKey="ram" data={chartData} color="hsl(var(--warning))" />
        <ChartCard title="Disk %" dataKey="disk" data={chartData} color="hsl(var(--healthy))" />
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
}: {
  title: string;
  dataKey: string;
  data: Array<Record<string, string | number | null>>;
  color: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--card-border))" />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
            <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--card-border))" }} />
            <Line type="monotone" dataKey={dataKey} stroke={color} dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
