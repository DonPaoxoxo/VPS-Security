import { FileText } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";

export default function ReportsPage() {
  return (
    <div>
      <PageHeader title="Reports" />
      <div className="rounded-xl border border-dashed border-card-border bg-card/50">
        <EmptyState
          icon={FileText}
          title="PDF reporting is planned for Phase 3"
          description="Every data source this page would report on (uptime history, security events, incidents) is already being collected — this view will be wired up once report generation is built."
        />
      </div>
    </div>
  );
}
