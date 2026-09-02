"use client";

import { useState } from "react";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import { formatTimestamp } from "./ConceptsPanel";
import type { SearchResult, SearchResultType } from "@/lib/types";

const TYPE_LABEL: Record<SearchResultType, string> = {
  CONCEPT: "Concept",
  RULE: "Rule",
  TRANSCRIPT: "Transcript",
};

const TYPE_TONE: Record<SearchResultType, "neutral" | "success" | "info"> = {
  CONCEPT: "success",
  RULE: "info",
  TRANSCRIPT: "neutral",
};

const ALL_TYPES: SearchResultType[] = ["CONCEPT", "RULE", "TRANSCRIPT"];

export function SearchPanel({ projectId }: { projectId: string }) {
  const api = useApi();
  const [query, setQuery] = useState("");
  const [activeTypes, setActiveTypes] = useState<SearchResultType[]>(ALL_TYPES);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchedFor, setSearchedFor] = useState<string | null>(null);

  function toggleType(t: SearchResultType) {
    setActiveTypes((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const types = activeTypes.length ? activeTypes : ALL_TYPES;
      const found = await api.search(projectId, query.trim(), { types });
      setResults(found);
      setSearchedFor(query.trim());
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Search"
        subtitle="Full-text search across every concept, rule, and raw transcript ingested for this project. Every result cites the video and timestamp it came from — nothing is returned without a source."
      />

      <form onSubmit={handleSearch} className="mb-4 flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. order block, liquidity sweep, kill zone..."
          className="flex-1"
        />
        <Button type="submit" disabled={loading || !query.trim()}>
          {loading && <Spinner />} Search
        </Button>
      </form>

      <div className="mb-4 flex gap-2">
        {ALL_TYPES.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => toggleType(t)}
            className={`rounded-full border px-3 py-1 text-xs font-medium uppercase tracking-wide ${
              activeTypes.includes(t)
                ? "border-accent-info text-slate-100"
                : "border-base-700 text-slate-600"
            }`}
          >
            {TYPE_LABEL[t]}
          </button>
        ))}
      </div>

      {results === null && !loading && (
        <p className="text-xs text-slate-600">Search results will appear here.</p>
      )}
      {results !== null && results.length === 0 && (
        <EmptyState title={`No results for "${searchedFor}"`} />
      )}
      {results !== null && results.length > 0 && (
        <div className="space-y-3">
          {results.map((r) => (
            <div key={`${r.result_type}-${r.id}`} className="rounded-md border border-base-700 bg-base-850 p-3">
              <div className="mb-1 flex items-center gap-2">
                <Badge tone={TYPE_TONE[r.result_type]}>{TYPE_LABEL[r.result_type]}</Badge>
                {r.evidence_type && <Badge tone="neutral">{r.evidence_type.replace(/_/g, " ")}</Badge>}
                {r.status && <Badge tone="neutral">{r.status.replace(/_/g, " ")}</Badge>}
                {r.title && <span className="text-xs font-medium text-slate-400">{r.title.replace(/_/g, " ")}</span>}
              </div>
              <p className="text-sm text-slate-200">{r.snippet}</p>
              {r.citations.length > 0 && (
                <div className="mt-2 space-y-1">
                  {r.citations.map((c, i) => (
                    <p key={i} className="text-[11px] text-slate-600">
                      <span className="text-slate-500">
                        {c.video_title} [{formatTimestamp(c.start_seconds)}–{formatTimestamp(c.end_seconds)}]
                      </span>{" "}
                      &ldquo;{c.excerpt}&rdquo;
                    </p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
