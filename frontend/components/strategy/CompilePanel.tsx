"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ErrorNote, Spinner } from "@/components/ui/Spinner";
import type { Rule } from "@/lib/types";

export function CompilePanel({
  projectId,
  strategyId,
  onCompiled,
}: {
  projectId: string;
  strategyId: string;
  onCompiled: () => void;
}) {
  const api = useApi();
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [compiling, setCompiling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listRules(projectId).then((all) => {
      const compilable = all.filter((r) => r.status === "USER_CONFIRMED" || r.status === "USER_MODIFIED");
      setRules(compilable);
      setSelected(new Set(compilable.map((r) => r.id)));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleCompile() {
    setCompiling(true);
    setError(null);
    try {
      await api.compileVersion(strategyId, Array.from(selected));
      onCompiled();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to compile strategy version.");
    } finally {
      setCompiling(false);
    }
  }

  if (!rules) return <Spinner />;

  if (rules.length === 0) {
    return (
      <ErrorNote message="No approved rules yet. Go to Knowledge and approve (or manually add) rules before compiling a strategy version." />
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">
        Only <Badge tone="success">USER_CONFIRMED</Badge> / <Badge tone="success">USER_MODIFIED</Badge> rules can be
        compiled. Select which ones to include in the new version.
      </p>
      <div className="max-h-72 space-y-1 overflow-y-auto rounded-md border border-base-700 bg-base-850 p-2">
        {rules.map((r) => (
          <label key={r.id} className="flex items-start gap-2 rounded p-1.5 text-xs hover:bg-base-800">
            <input type="checkbox" checked={selected.has(r.id)} onChange={() => toggle(r.id)} className="mt-0.5" />
            <span>
              <Badge tone="neutral" className="mr-1">
                {r.category.replace(/_/g, " ")}
              </Badge>
              {r.natural_language_rule}
            </span>
          </label>
        ))}
      </div>
      {error && <ErrorNote message={error} />}
      <Button onClick={handleCompile} disabled={compiling || selected.size === 0}>
        {compiling && <Spinner />} Compile version ({selected.size} rules)
      </Button>
    </div>
  );
}
