"use client";

import { useState } from "react";
import { useApi } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import type { StrategyVersion } from "@/lib/types";

export function VersionsView({ versions }: { versions: StrategyVersion[] }) {
  const api = useApi();
  const [fromId, setFromId] = useState<string>("");
  const [toId, setToId] = useState<string>("");
  const [diff, setDiff] = useState<Record<string, { before: unknown; after: unknown }> | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCompare() {
    if (!fromId || !toId) return;
    setLoading(true);
    try {
      const result = await api.compareVersions(fromId, toId);
      setDiff(result.changes);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="divide-y divide-base-800">
        {[...versions].reverse().map((v) => (
          <div key={v.id} className="flex items-center justify-between py-2 text-sm">
            <div>
              <span className="font-medium text-slate-200">{v.label ?? `v${v.version_number}`}</span>{" "}
              <span className="text-xs text-slate-500">{v.change_summary}</span>
            </div>
            <Badge tone={v.completeness_score === 100 ? "success" : "warn"}>{v.completeness_score}% complete</Badge>
          </div>
        ))}
      </div>

      {versions.length > 1 && (
        <div className="rounded-md border border-base-700 bg-base-850 p-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Compare versions</p>
          <div className="flex items-center gap-2">
            <VersionSelect versions={versions} value={fromId} onChange={setFromId} placeholder="From" />
            <span className="text-slate-500">vs</span>
            <VersionSelect versions={versions} value={toId} onChange={setToId} placeholder="To" />
            <Button variant="secondary" onClick={handleCompare} disabled={!fromId || !toId || loading}>
              {loading && <Spinner />} Compare
            </Button>
          </div>
          {diff && (
            <div className="mt-3 space-y-2">
              {Object.keys(diff).length === 0 && <p className="text-xs text-slate-500">No differences.</p>}
              {Object.entries(diff).map(([field, change]) => (
                <div key={field} className="rounded bg-base-900 p-2 text-xs">
                  <p className="font-medium text-slate-300">{field}</p>
                  <p className="text-accent-short">- {JSON.stringify(change.before)}</p>
                  <p className="text-accent-long">+ {JSON.stringify(change.after)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function VersionSelect({
  versions,
  value,
  onChange,
  placeholder,
}: {
  versions: StrategyVersion[];
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-md border border-base-600 bg-base-900 px-2 py-1.5 text-sm text-slate-200">
      <option value="">{placeholder}</option>
      {versions.map((v) => (
        <option key={v.id} value={v.id}>
          {v.label ?? `v${v.version_number}`}
        </option>
      ))}
    </select>
  );
}
