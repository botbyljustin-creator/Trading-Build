"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Tabs } from "@/components/ui/Tabs";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import { CompilePanel } from "@/components/strategy/CompilePanel";
import { PlaybookView } from "@/components/strategy/PlaybookView";
import { CodeView } from "@/components/strategy/CodeView";
import { BacktestsView } from "@/components/strategy/BacktestsView";
import { VersionsView } from "@/components/strategy/VersionsView";
import { RulesPanel } from "@/components/knowledge/RulesPanel";
import { ConceptsPanel } from "@/components/knowledge/ConceptsPanel";
import type { SourceRecord, Strategy } from "@/lib/types";

export default function StrategyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const api = useApi();
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [showCompile, setShowCompile] = useState(false);

  async function refresh() {
    const s = await api.getStrategy(id);
    setStrategy(s);
    const lastVersion = s.versions.at(-1);
    if (!selectedVersionId && lastVersion) {
      setSelectedVersionId(lastVersion.id);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!strategy) return <Spinner />;

  const selectedVersion = strategy.versions.find((v) => v.id === selectedVersionId) ?? null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">{strategy.name}</h1>
          <p className="text-xs text-slate-500">{strategy.description}</p>
        </div>
        {strategy.versions.length > 0 && (
          <select
            value={selectedVersionId ?? ""}
            onChange={(e) => setSelectedVersionId(e.target.value)}
            className="rounded-md border border-base-600 bg-base-900 px-2 py-1.5 text-sm text-slate-200"
          >
            {[...strategy.versions].reverse().map((v) => (
              <option key={v.id} value={v.id}>
                {v.label ?? `v${v.version_number}`} ({v.completeness_score}%)
              </option>
            ))}
          </select>
        )}
      </div>

      <Tabs
        items={[
          {
            key: "overview",
            label: "Overview",
            content: (
              <Card>
                <CardHeader
                  title="Overview"
                  action={
                    <button onClick={() => setShowCompile((v) => !v)} className="text-xs text-accent-info hover:underline">
                      {showCompile ? "Cancel" : "Compile new version"}
                    </button>
                  }
                />
                {showCompile && (
                  <div className="mb-4">
                    <CompilePanel
                      projectId={strategy.project_id}
                      strategyId={strategy.id}
                      onCompiled={() => {
                        setShowCompile(false);
                        refresh();
                      }}
                    />
                  </div>
                )}
                {selectedVersion ? (
                  <div className="space-y-2 text-sm">
                    <p>
                      Current version: <strong>{selectedVersion.label}</strong>
                    </p>
                    <p>
                      Completeness:{" "}
                      <Badge tone={selectedVersion.completeness_score === 100 ? "success" : "warn"}>
                        {selectedVersion.completeness_score}%
                      </Badge>
                    </p>
                    <p className="text-xs text-slate-500">{selectedVersion.change_summary}</p>
                  </div>
                ) : (
                  <EmptyState title="No versions compiled yet" description="Compile a version from approved rules to get started." />
                )}
              </Card>
            ),
          },
          {
            key: "sources",
            label: "Sources",
            content: <SourcesReadOnly projectId={strategy.project_id} />,
          },
          {
            key: "concepts",
            label: "Concepts",
            content: <ConceptsPanel projectId={strategy.project_id} />,
          },
          {
            key: "rules",
            label: "Rules",
            content: <RulesPanel projectId={strategy.project_id} />,
          },
          {
            key: "playbook",
            label: "Playbook",
            content: selectedVersion ? (
              <Card>
                <CardHeader title="Trading Playbook" subtitle="Structured strategy specification for the selected version." />
                <PlaybookView versionId={selectedVersion.id} missingFields={selectedVersion.missing_fields} />
              </Card>
            ) : (
              <EmptyState title="Compile a version first" />
            ),
          },
          {
            key: "code",
            label: "Code",
            content: selectedVersion ? (
              <Card>
                <CardHeader title="Generated Code" subtitle="Pine Script and Python, generated from the same specification." />
                <CodeView versionId={selectedVersion.id} />
              </Card>
            ) : (
              <EmptyState title="Compile a version first" />
            ),
          },
          {
            key: "backtests",
            label: "Backtests",
            content: selectedVersion ? (
              <Card>
                <CardHeader title="Backtests" />
                <BacktestsView versionId={selectedVersion.id} />
              </Card>
            ) : (
              <EmptyState title="Compile a version first" />
            ),
          },
          {
            key: "versions",
            label: "Versions",
            content: (
              <Card>
                <CardHeader title="Version History" />
                <VersionsView versions={strategy.versions} />
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}

function SourcesReadOnly({ projectId }: { projectId: string }) {
  const api = useApi();
  const [sources, setSources] = useState<SourceRecord[] | null>(null);

  useEffect(() => {
    api.listSources(projectId).then(setSources);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return (
    <Card>
      <CardHeader title="Sources" subtitle="Manage sources from the Sources page." />
      {!sources && <Spinner />}
      {sources && sources.length === 0 && <EmptyState title="No sources in this project yet." />}
      {sources && sources.length > 0 && (
        <div className="divide-y divide-base-800">
          {sources.map((s) => (
            <div key={s.id} className="flex items-center justify-between py-2 text-sm">
              <span className="truncate text-slate-300">{s.title ?? s.url}</span>
              <Badge tone={s.status === "READY" ? "success" : "neutral"}>{s.status}</Badge>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
