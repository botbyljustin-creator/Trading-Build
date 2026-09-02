"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useJobPolling } from "@/lib/useJobPolling";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge, JobStatusBadge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import type { Concept } from "@/lib/types";

export function ConceptsPanel({ projectId }: { projectId: string }) {
  const api = useApi();
  const [concepts, setConcepts] = useState<Concept[] | null>(null);
  const { job, track, isActive } = useJobPolling();

  async function refresh() {
    setConcepts(await api.listConcepts(projectId));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (job?.status === "SUCCESS") refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  async function handleExtract() {
    const j = await api.extractConcepts(projectId);
    track(j);
  }

  return (
    <Card>
      <CardHeader
        title="Concepts"
        subtitle="Trading concepts actually present in the source material — never assumed."
        action={
          <div className="flex items-center gap-2">
            {job && <JobStatusBadge status={job.status} />}
            <Button onClick={handleExtract} disabled={isActive}>
              {isActive && <Spinner />} Extract concepts
            </Button>
          </div>
        }
      />
      {job?.status === "FAILED" && <p className="mb-3 text-xs text-accent-short">{job.error_message}</p>}
      {!concepts && <Spinner />}
      {concepts && concepts.length === 0 && (
        <EmptyState
          title="No concepts extracted yet"
          description="Run extraction after transcripts are available for at least one video."
        />
      )}
      {concepts && concepts.length > 0 && (
        <div className="space-y-3">
          {concepts.map((c) => (
            <div key={c.id} className="rounded-md border border-base-700 bg-base-850 p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-200">{c.name}</p>
                <Badge tone="info">{Math.round(c.confidence * 100)}% confidence</Badge>
              </div>
              <p className="mt-1 text-xs text-slate-400">{c.description}</p>
              <div className="mt-2 space-y-1">
                {c.sources.map((s) => (
                  <p key={s.id} className="text-[11px] text-slate-600">
                    <span className="text-slate-500">
                      [{formatTimestamp(s.start_seconds)}–{formatTimestamp(s.end_seconds)}]
                    </span>{" "}
                    &ldquo;{s.excerpt}&rdquo;
                  </p>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
