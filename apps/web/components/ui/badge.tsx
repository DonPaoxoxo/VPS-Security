import { type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type BadgeTone = "healthy" | "warning" | "critical" | "info" | "muted";

const toneClasses: Record<BadgeTone, string> = {
  healthy: "bg-healthy/15 text-healthy border-healthy/30",
  warning: "bg-warning/15 text-warning border-warning/30",
  critical: "bg-critical/15 text-critical border-critical/30",
  info: "bg-info/15 text-info border-info/30",
  muted: "bg-muted text-muted-foreground border-card-border",
};

export function Badge({
  className,
  tone = "muted",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}

export function toneForStatus(status: string): BadgeTone {
  const healthy = ["connected", "healthy", "up", "active", "approved", "resolved", "running"];
  const warning = ["pending", "degraded", "acknowledged", "warning", "access_restricted"];
  const critical = ["disconnected", "unreachable", "down", "critical", "service_stopped", "open"];
  if (healthy.includes(status)) return "healthy";
  if (warning.includes(status)) return "warning";
  if (critical.includes(status)) return "critical";
  return "muted";
}
