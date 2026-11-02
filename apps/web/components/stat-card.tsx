import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/cn";

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: number | string;
  icon: LucideIcon;
  tone?: "default" | "healthy" | "warning" | "critical" | "info";
}) {
  const toneClasses = {
    default: { text: "text-foreground", badge: "bg-muted text-muted-foreground" },
    healthy: { text: "text-healthy", badge: "bg-healthy/10 text-healthy" },
    warning: { text: "text-warning", badge: "bg-warning/10 text-warning" },
    critical: { text: "text-critical", badge: "bg-critical/10 text-critical" },
    info: { text: "text-info", badge: "bg-info/10 text-info" },
  } as const;

  return (
    <Card interactive>
      <CardContent className="flex items-center justify-between gap-3 p-5">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-muted-foreground">{label}</p>
          <p className={cn("mt-1.5 text-2xl font-semibold tracking-tight", toneClasses[tone].text)}>{value}</p>
        </div>
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", toneClasses[tone].badge)}>
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  );
}
