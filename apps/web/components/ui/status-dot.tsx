import { cn } from "@/lib/cn";
import type { BadgeTone } from "@/components/ui/badge";

const toneClasses: Record<BadgeTone, string> = {
  healthy: "bg-healthy",
  warning: "bg-warning",
  critical: "bg-critical",
  info: "bg-info",
  muted: "bg-muted-foreground",
};

export function StatusDot({ tone, pulse = false }: { tone: BadgeTone; pulse?: boolean }) {
  return (
    <span className="relative flex h-2 w-2">
      {pulse && (
        <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", toneClasses[tone])} />
      )}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", toneClasses[tone])} />
    </span>
  );
}
