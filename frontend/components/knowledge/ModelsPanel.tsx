"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import type { ModelReadiness } from "@/lib/types";

function scoreTone(score: number): "success" | "warn" | "danger" {
  if (score >= 70) return "success";
  if (score >= 40) return "warn";
  return "danger";
}

export function ModelsPanel({ projectId }: { projectId: string }) {
  const api = useApi();
  const [models, setModels] = useState<ModelReadiness[] | null>(null);

  useEffect(() => {
    api.getModelReadiness(projectId).then(setModels);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return (
    <Card>
      <CardHeader
        title="Models"
        subtitle="One candidate model per series — never flattened into a single strategy. Ranked by how close each one is to backtestable, not by backtesting everything at once."
      />

      {!models && <Spinner />}
      {models && models.length === 0 && (
        <EmptyState title="No rules yet" description="Extract or add rules first — a model needs at least one to score." />
      )}
      {models && models.length > 0 && (
        <div className="space-y-3">
          {models.map((m) => (
            <div key={m.series_id ?? "ungrouped"} className="rounded-md border border-base-700 bg-base-850 p-3">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-100">{m.series_name}</p>
                  {m.creator_name && <p className="text-xs text-slate-500">{m.creator_name}</p>}
                </div>
                <Badge tone={scoreTone(m.score)}>{m.score.toFixed(1)} / 100</Badge>
              </div>

              <div className="mb-2 flex flex-wrap gap-2 text-[11px] text-slate-500">
                <span>{m.total_rules} rules</span>
                <span>{m.explicit_rules} explicit</span>
                <span>{m.fully_quantifiable_rules} fully quantifiable</span>
                <span>{m.partially_quantifiable_rules} partially quantifiable</span>
                <span>{m.discretionary_rules} discretionary</span>
                <span>{m.nasdaq_relevant_rules} NASDAQ-tagged</span>
                {m.unresolved_contradictions > 0 && (
                  <span className="text-accent-short">{m.unresolved_contradictions} in unresolved contradictions</span>
                )}
              </div>

              {m.categories_missing.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {m.categories_missing.map((c) => (
                    <Badge key={c} tone="warn">
                      missing: {c.replace(/_/g, " ")}
                    </Badge>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap gap-3 text-[10px] text-slate-600">
                {Object.entries(m.score_breakdown).map(([key, value]) => (
                  <span key={key}>
                    {key.replace(/_/g, " ")}: {value >= 0 ? "+" : ""}
                    {value}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
