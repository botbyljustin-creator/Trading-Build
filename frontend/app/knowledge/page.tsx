"use client";

import { RequireProject } from "@/components/RequireProject";
import { Tabs } from "@/components/ui/Tabs";
import { ConceptsPanel } from "@/components/knowledge/ConceptsPanel";
import { RulesPanel } from "@/components/knowledge/RulesPanel";
import { ContradictionsPanel } from "@/components/knowledge/ContradictionsPanel";
import { SearchPanel } from "@/components/knowledge/SearchPanel";

export default function KnowledgePage() {
  return (
    <RequireProject>
      {(projectId) => (
        <div className="space-y-6">
          <h1 className="text-lg font-semibold text-slate-100">Knowledge</h1>
          <Tabs
            items={[
              { key: "search", label: "Search", content: <SearchPanel projectId={projectId} /> },
              { key: "rules", label: "Rules", content: <RulesPanel projectId={projectId} /> },
              { key: "concepts", label: "Concepts", content: <ConceptsPanel projectId={projectId} /> },
              {
                key: "contradictions",
                label: "Contradictions",
                content: <ContradictionsPanel projectId={projectId} />,
              },
            ]}
          />
        </div>
      )}
    </RequireProject>
  );
}
