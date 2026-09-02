"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireProject } from "@/components/RequireProject";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Spinner";
import type { Strategy } from "@/lib/types";

export default function StrategiesPage() {
  return <RequireProject>{(projectId) => <StrategiesForProject projectId={projectId} />}</RequireProject>;
}

function StrategiesForProject({ projectId }: { projectId: string }) {
  const api = useApi();
  const [strategies, setStrategies] = useState<Strategy[] | null>(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setStrategies(await api.listStrategies(projectId));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.createStrategy(projectId, { name });
      setName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create strategy.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Strategies</h1>

      <Card>
        <CardHeader title="New strategy" />
        <form onSubmit={handleCreate} className="flex gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Morning Reversal System" />
          <Button type="submit" disabled={creating}>
            {creating && <Spinner />} Create
          </Button>
        </form>
        {error && <div className="mt-2"><ErrorNote message={error} /></div>}
      </Card>

      <Card>
        <CardHeader title="Strategies" />
        {!strategies && <Spinner />}
        {strategies && strategies.length === 0 && (
          <EmptyState title="No strategies yet" description="Approve some rules in Knowledge, then create a strategy and compile a version from them." />
        )}
        {strategies && strategies.length > 0 && (
          <div className="divide-y divide-base-800">
            {strategies.map((s) => {
              const latest = s.versions[s.versions.length - 1];
              return (
                <Link key={s.id} href={`/strategies/${s.id}`} className="flex items-center justify-between py-3 hover:bg-base-850">
                  <div>
                    <p className="text-sm font-medium text-slate-200">{s.name}</p>
                    <p className="text-xs text-slate-500">
                      {s.versions.length} version{s.versions.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  {latest && (
                    <Badge tone={latest.completeness_score === 100 ? "success" : "warn"}>
                      {latest.label}: {latest.completeness_score}% complete
                    </Badge>
                  )}
                </Link>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
