import { FileText } from "lucide-react";

export default function ReportsPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold">Reports</h1>
      <div className="mt-8 flex flex-col items-center gap-3 rounded-lg border border-dashed border-card-border py-16 text-center">
        <FileText className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium">PDF reporting is planned for Phase 3</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          Every data source this page would report on (uptime history, security events, incidents) is already being
          collected — this view will be wired up once report generation is built.
        </p>
      </div>
    </div>
  );
}
