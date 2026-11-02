import { cn } from "@/lib/cn";

function toneForUsage(pct: number): string {
  if (pct >= 90) return "bg-critical";
  if (pct >= 75) return "bg-warning";
  return "bg-accent";
}

export function UsageBar({ value, className }: { value: number | null; className?: string }) {
  if (value === null) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all", toneForUsage(pct))}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-xs tabular-nums text-muted-foreground">{pct.toFixed(0)}%</span>
    </div>
  );
}
