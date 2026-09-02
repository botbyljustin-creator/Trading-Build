"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireProject } from "@/components/RequireProject";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import type { Report } from "@/lib/types";

export default function ReportsPage() {
  return <RequireProject>{(projectId) => <ReportsForProject projectId={projectId} />}</RequireProject>;
}

function ReportsForProject({ projectId }: { projectId: string }) {
  const api = useApi();
  const [reports, setReports] = useState<Report[] | null>(null);

  useEffect(() => {
    api.listProjectReports(projectId).then(setReports).catch(() => setReports([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Reports</h1>
      <Card>
        <CardHeader title="Generated reports" subtitle="Generate one from a backtest's page." />
        {!reports && <Spinner />}
        {reports && reports.length === 0 && <EmptyState title="No reports generated yet." />}
        {reports && reports.length > 0 && (
          <div className="divide-y divide-base-800">
            {reports.map((r) => (
              <Link key={r.id} href={`/reports/view/${r.id}`} className="block py-3 text-sm hover:bg-base-850">
                <p className="text-slate-200">
                  {(r.content_json.strategy_summary as any)?.name ?? "Strategy report"} &middot; v
                  {(r.content_json.strategy_version as number) ?? "?"}
                </p>
                <p className="text-xs text-slate-500">{new Date(r.created_at).toLocaleString()}</p>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
