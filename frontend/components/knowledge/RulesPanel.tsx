"use client";

import { useEffect, useMemo, useState } from "react";
import { useApi } from "@/lib/api";
import { useJobPolling } from "@/lib/useJobPolling";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { RuleStatusBadge, JobStatusBadge, Badge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import { Textarea } from "@/components/ui/Input";
import { formatTimestamp } from "./ConceptsPanel";
import type { Rule, RuleCategory } from "@/lib/types";

const GROUPS: { key: string; label: string; statuses: Rule["status"][] }[] = [
  { key: "confirmed", label: "Confirmed", statuses: ["USER_CONFIRMED", "USER_MODIFIED"] },
  { key: "review", label: "Needs Review", statuses: ["EXTRACTED", "AMBIGUOUS", "AI_ASSUMPTION"] },
  { key: "contradictory", label: "Contradictory", statuses: ["CONTRADICTORY"] },
  { key: "rejected", label: "Rejected", statuses: ["REJECTED"] },
];

const CATEGORIES: RuleCategory[] = [
  "MARKET",
  "TIMEFRAME",
  "SESSION",
  "MARKET_REGIME",
  "BIAS",
  "SETUP",
  "ENTRY",
  "CONFIRMATION",
  "STOP_LOSS",
  "TAKE_PROFIT",
  "POSITION_SIZING",
  "TRADE_MANAGEMENT",
  "INVALIDATION",
  "NO_TRADE_CONDITIONS",
];

export function RulesPanel({ projectId }: { projectId: string }) {
  const api = useApi();
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [activeGroup, setActiveGroup] = useState("review");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [manualOpen, setManualOpen] = useState(false);
  const { job, track, isActive } = useJobPolling();

  async function refresh() {
    setRules(await api.listRules(projectId));
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
    track(await api.extractRules(projectId));
  }

  async function handleApprove(id: string) {
    await api.approveRule(id);
    await refresh();
  }

  async function handleReject(id: string) {
    await api.rejectRule(id);
    await refresh();
  }

  async function handleSaveEdit(id: string) {
    await api.updateRule(id, { natural_language_rule: editText });
    setEditingId(null);
    await refresh();
  }

  const grouped = useMemo(() => {
    const map: Record<string, Rule[]> = {};
    for (const group of GROUPS) map[group.key] = [];
    for (const rule of rules ?? []) {
      const group = GROUPS.find((g) => g.statuses.includes(rule.status));
      if (group) map[group.key]?.push(rule);
    }
    return map;
  }, [rules]);

  return (
    <Card>
      <CardHeader
        title="Rules"
        subtitle="Every rule traces to a source. AI_ASSUMPTION rules require explicit approval before they can enter a strategy."
        action={
          <div className="flex items-center gap-2">
            {job && <JobStatusBadge status={job.status} />}
            <Button variant="secondary" onClick={() => setManualOpen((v) => !v)}>
              + Add rule manually
            </Button>
            <Button onClick={handleExtract} disabled={isActive}>
              {isActive && <Spinner />} Extract rules
            </Button>
          </div>
        }
      />
      {job?.status === "FAILED" && <p className="mb-3 text-xs text-accent-short">{job.error_message}</p>}

      {manualOpen && <ManualRuleForm projectId={projectId} onCreated={() => { setManualOpen(false); refresh(); }} />}

      <div className="mb-4 flex gap-1 border-b border-base-800">
        {GROUPS.map((g) => (
          <button
            key={g.key}
            onClick={() => setActiveGroup(g.key)}
            className={`px-3 py-2 text-xs font-medium uppercase tracking-wide ${
              activeGroup === g.key ? "border-b-2 border-accent-info text-slate-100" : "text-slate-500"
            }`}
          >
            {g.label} ({grouped[g.key]?.length ?? 0})
          </button>
        ))}
      </div>

      {!rules && <Spinner />}
      {rules && (grouped[activeGroup]?.length ?? 0) === 0 && (
        <EmptyState title={`No rules in "${GROUPS.find((g) => g.key === activeGroup)?.label}"`} />
      )}
      {rules && (
        <div className="space-y-3">
          {grouped[activeGroup]?.map((rule) => (
            <div key={rule.id} className="rounded-md border border-base-700 bg-base-850 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge tone="neutral">{rule.category.replace(/_/g, " ")}</Badge>
                    <RuleStatusBadge status={rule.status} />
                    {rule.is_user_provided && <Badge tone="info">user-provided</Badge>}
                    <span className="text-[10px] text-slate-600">{Math.round(rule.confidence * 100)}% confidence</span>
                  </div>
                  {editingId === rule.id ? (
                    <div className="space-y-2">
                      <Textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={2} />
                      <div className="flex gap-2">
                        <Button onClick={() => handleSaveEdit(rule.id)}>Save</Button>
                        <Button variant="secondary" onClick={() => setEditingId(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-200">{rule.natural_language_rule}</p>
                  )}
                  {rule.sources.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {rule.sources.map((s) => (
                        <p key={s.id} className="text-[11px] text-slate-600">
                          <span className="text-slate-500">
                            [{formatTimestamp(s.start_seconds)}–{formatTimestamp(s.end_seconds)}]
                          </span>{" "}
                          &ldquo;{s.excerpt}&rdquo;
                        </p>
                      ))}
                    </div>
                  )}
                </div>
                {editingId !== rule.id && (
                  <div className="flex shrink-0 flex-col gap-1">
                    {rule.status !== "USER_CONFIRMED" && rule.status !== "USER_MODIFIED" && (
                      <Button variant="secondary" onClick={() => handleApprove(rule.id)}>
                        Approve
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setEditingId(rule.id);
                        setEditText(rule.natural_language_rule);
                      }}
                    >
                      Edit
                    </Button>
                    {rule.status !== "REJECTED" && (
                      <Button variant="danger" onClick={() => handleReject(rule.id)}>
                        Reject
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ManualRuleForm({ projectId, onCreated }: { projectId: string; onCreated: () => void }) {
  const api = useApi();
  const [category, setCategory] = useState<RuleCategory>("ENTRY");
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    try {
      await api.createManualRule(projectId, { category, natural_language_rule: text });
      setText("");
      onCreated();
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-4 space-y-2 rounded-md border border-base-700 bg-base-850 p-3">
      <p className="text-xs text-slate-500">
        Use this to fill a gap the Strategy Auditor flagged as missing — this is recorded as something{" "}
        <em>you</em> defined, not a claim about what the creator said.
      </p>
      <div className="flex gap-2">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as RuleCategory)}
          className="rounded-md border border-base-600 bg-base-900 px-2 py-1.5 text-sm text-slate-200"
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={1} placeholder="e.g. Maximum 2 trades per day" />
        <Button type="submit" disabled={saving}>
          {saving && <Spinner />} Add
        </Button>
      </div>
    </form>
  );
}
