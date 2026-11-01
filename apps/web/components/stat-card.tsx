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
  tone?: "default" | "healthy" | "warning" | "critical";
}) {
  const toneClasses = {
    default: "text-foreground",
    healthy: "text-healthy",
    warning: "text-warning",
    critical: "text-critical",
  } as const;

  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className={cn("mt-1 text-2xl font-semibold", toneClasses[tone])}>{value}</p>
        </div>
        <Icon className="h-8 w-8 text-muted-foreground opacity-60" />
      </CardContent>
    </Card>
  );
}
