"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useJobPolling } from "@/lib/useJobPolling";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge, JobStatusBadge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import type { Contradiction, ContradictionResolution, Rule } from "@/lib/types";

const RESOLUTION_TONE: Record<ContradictionResolution, "neutral" | "success" | "warn"> = {
  UNRESOLVED: "warn",
  USE_A: "success",
  USE_B: "success",
  CONTEXT_DEPENDENT: "success",
  IGNORE: "neutral",
};

export function ContradictionsPanel({ projectId }: { projectId: string }) {
  const api = useApi();
  const [contradictions, setContradictions] = useState<Contradiction[] | null>(null);
  const [rulesById, setRulesById] = useState<Record<string, Rule>>({});
  const { job, track, isActive } = useJobPolling();

  async function refresh() {
    const [contra, rules] = await Promise.all([api.listContradictions(projectId), api.listRules(projectId)]);
    setContradictions(contra);
    setRulesById(Object.fromEntries(rules.map((r) => [r.id, r])));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (job?.status === "SUCCESS") refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  async function handleDetect() {
    track(await api.detectContradictions(projectId));
  }

  async function handleResolve(id: string, resolution: ContradictionResolution) {
    await api.resolveContradiction(id, resolution);
    await refresh();
  }

  return (
    <Card>
      <CardHeader
        title="Contradictions"
        subtitle="Creators change their approach over time. Conflicting rules are flagged, never auto-resolved."
        action={
          <div className="flex items-center gap-2">
            {job && <JobStatusBadge status={job.status} />}
            <Button onClick={handleDetect} disabled={isActive}>
              {isActive && <Spinner />} Detect contradictions
            </Button>
          </div>
        }
      />
      {job?.status === "FAILED" && <p className="mb-3 text-xs text-accent-short">{job.error_message}</p>}
      {!contradictions && <Spinner />}
      {contradictions && contradictions.length === 0 && (
        <EmptyState title="No contradictions detected" description="Run detection after extracting rules from multiple videos." />
      )}
      {contradictions && contradictions.length > 0 && (
        <div className="space-y-3">
          {contradictions.map((c) => {
            const ruleA = rulesById[c.rule_a_id];
            const ruleB = rulesById[c.rule_b_id];
            return (
              <div key={c.id} className="rounded-md border border-base-700 bg-base-850 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <Badge tone={RESOLUTION_TONE[c.resolution]}>{c.resolution.replace(/_/g, " ")}</Badge>
                </div>
                <p className="mb-2 text-xs text-slate-400">{c.explanation}</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <RuleSnippet label="Rule A" rule={ruleA} />
                  <RuleSnippet label="Rule B" rule={ruleB} />
                </div>
                <div className="mt-3 flex gap-2">
                  <Button variant="secondary" onClick={() => handleResolve(c.id, "USE_A")}>
                    Use A
                  </Button>
                  <Button variant="secondary" onClick={() => handleResolve(c.id, "USE_B")}>
                    Use B
                  </Button>
                  <Button variant="secondary" onClick={() => handleResolve(c.id, "CONTEXT_DEPENDENT")}>
                    Context dependent
                  </Button>
                  <Button variant="ghost" onClick={() => handleResolve(c.id, "IGNORE")}>
                    Ignore
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function RuleSnippet({ label, rule }: { label: string; rule?: Rule }) {
  return (
    <div className="rounded border border-base-700 bg-base-900 p-2">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-xs text-slate-300">{rule?.natural_language_rule ?? "Rule not found"}</p>
    </div>
  );
}
