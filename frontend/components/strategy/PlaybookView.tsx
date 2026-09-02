"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";

interface SpecShape {
  strategy_name: string;
  instrument: { market_description: string | null; timeframe: string | null };
  session: { start_time: string; end_time: string; timezone: string; days_of_week: number[] } | null;
  bias_rule: string | null;
  setup_rule: string | null;
  confirmation_rule: string | null;
  entry_rule: string | null;
  stop_loss: { method: string; value: number | null; description: string } | null;
  take_profit: { method: string; value: number | null; description: string } | null;
  position_sizing: { method: string; value: number; description: string } | null;
  max_trades_per_day: number | null;
  allow_long: boolean | null;
  allow_short: boolean | null;
  allow_overnight_positions: boolean | null;
  allow_multiple_concurrent_positions: boolean | null;
  invalidation_rule: string | null;
  no_trade_conditions: string[];
  trade_management_notes: string[];
}

export function PlaybookView({ versionId, missingFields }: { versionId: string; missingFields: string[] | null }) {
  const api = useApi();
  const [spec, setSpec] = useState<SpecShape | null | "none">(null);

  useEffect(() => {
    api
      .getVersionSpec(versionId)
      .then((s) => setSpec(s as unknown as SpecShape))
      .catch(() => setSpec("none"));
  }, [versionId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (spec === null) return <Spinner />;
  if (spec === "none") return <EmptyState title="No compiled specification for this version." />;

  return (
    <div className="space-y-4">
      {missingFields && missingFields.length > 0 && (
        <div className="rounded-md border border-accent-warn/30 bg-accent-warn/5 p-3 text-xs text-accent-warn">
          <p className="mb-1 font-semibold uppercase tracking-wide">Missing / incomplete</p>
          <ul className="list-inside list-disc space-y-0.5">
            {missingFields.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      <PlaybookRow label="Market" value={spec.instrument.market_description} />
      <PlaybookRow label="Timeframe" value={spec.instrument.timeframe} />
      <PlaybookRow
        label="Session"
        value={
          spec.session ? `${spec.session.start_time}–${spec.session.end_time} ${spec.session.timezone}` : null
        }
      />
      <PlaybookRow label="Bias" value={spec.bias_rule} />
      <PlaybookRow label="Setup" value={spec.setup_rule} />
      <PlaybookRow label="Confirmation" value={spec.confirmation_rule} />
      <PlaybookRow label="Entry" value={spec.entry_rule} />
      <PlaybookRow
        label="Stop Loss"
        value={spec.stop_loss ? `${spec.stop_loss.method}${spec.stop_loss.value != null ? ` (${spec.stop_loss.value})` : ""} — ${spec.stop_loss.description}` : null}
      />
      <PlaybookRow
        label="Take Profit"
        value={
          spec.take_profit
            ? `${spec.take_profit.method}${spec.take_profit.value != null ? ` (${spec.take_profit.value})` : ""} — ${spec.take_profit.description}`
            : null
        }
      />
      <PlaybookRow
        label="Risk / Position Sizing"
        value={spec.position_sizing ? `${spec.position_sizing.method}: ${spec.position_sizing.value} — ${spec.position_sizing.description}` : null}
      />
      <PlaybookRow label="Max trades/day" value={spec.max_trades_per_day?.toString() ?? null} />
      <PlaybookRow
        label="Direction"
        value={
          spec.allow_long == null && spec.allow_short == null
            ? null
            : [spec.allow_long ? "Long" : null, spec.allow_short ? "Short" : null].filter(Boolean).join(" + ") || "Neither"
        }
      />
      <PlaybookRow
        label="Overnight positions"
        value={spec.allow_overnight_positions == null ? null : spec.allow_overnight_positions ? "Allowed" : "Not allowed"}
      />
      <PlaybookRow
        label="Concurrent positions"
        value={spec.allow_multiple_concurrent_positions == null ? null : spec.allow_multiple_concurrent_positions ? "Multiple allowed" : "One at a time"}
      />
      <PlaybookRow label="Invalidation" value={spec.invalidation_rule} />
      <PlaybookRow label="No-trade conditions" value={spec.no_trade_conditions.join("; ") || null} />
      <PlaybookRow label="Trade management notes" value={spec.trade_management_notes.join("; ") || null} />
    </div>
  );
}

function PlaybookRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-start gap-4 border-b border-base-800 py-2 text-sm">
      <span className="w-40 shrink-0 text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      {value ? <span className="text-slate-200">{value}</span> : <Badge tone="warn">Not defined</Badge>}
    </div>
  );
}
