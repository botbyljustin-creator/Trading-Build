"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { useJobPolling } from "@/lib/useJobPolling";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Input";
import { Badge, JobStatusBadge } from "@/components/ui/Badge";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Spinner";
import type { Backtest } from "@/lib/types";

const STATUS_TONE: Record<string, "neutral" | "success" | "danger" | "warn" | "info"> = {
  PENDING: "neutral",
  RUNNING: "info",
  COMPLETE: "success",
  FAILED: "danger",
};

export function BacktestsView({ versionId }: { versionId: string }) {
  const api = useApi();
  const [backtests, setBacktests] = useState<Backtest[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { job, track, isActive } = useJobPolling();

  const [form, setForm] = useState({
    symbol: "",
    provider: "csv",
    timezone: "America/New_York",
    asset_type: "CFD",
    date_start: "",
    date_end: "",
    starting_balance: 10000,
    risk_pct_per_trade: 1,
    commission_per_trade: 0,
    slippage_pct: 0,
    max_trades_per_day: "",
  });

  async function refresh() {
    setBacktests(await api.listBacktests(versionId));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionId]);

  useEffect(() => {
    if (job?.status === "SUCCESS") {
      refresh();
      setShowForm(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const j = await api.createBacktest(versionId, {
        provider: form.provider,
        symbol: form.symbol,
        timezone: form.timezone,
        asset_type: form.asset_type,
        date_start: new Date(form.date_start).toISOString(),
        date_end: new Date(form.date_end).toISOString(),
        starting_balance: Number(form.starting_balance),
        risk_pct_per_trade: Number(form.risk_pct_per_trade),
        commission_per_trade: Number(form.commission_per_trade),
        slippage_pct: Number(form.slippage_pct),
        max_trades_per_day: form.max_trades_per_day ? Number(form.max_trades_per_day) : undefined,
      });
      track(j);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start backtest.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">
          Backtests require a CSV data file named <code>&lt;symbol&gt;.csv</code> in the market data directory (see
          docs/BACKTESTING.md). Provider/symbol/timezone are always explicit — never assumed.
        </p>
        <div className="flex items-center gap-2">
          {job && <JobStatusBadge status={job.status} />}
          <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Run new backtest"}</Button>
        </div>
      </div>

      {job?.status === "FAILED" && <ErrorNote message={job.error_message ?? "Backtest failed."} />}

      {showForm && (
        <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-3 rounded-md border border-base-700 bg-base-850 p-4 md:grid-cols-4">
          <Field label="Symbol"><Input required value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} placeholder="e.g. NAS100_CSV" /></Field>
          <Field label="Provider"><Input value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} /></Field>
          <Field label="Asset Type"><Input value={form.asset_type} onChange={(e) => setForm({ ...form, asset_type: e.target.value })} /></Field>
          <Field label="Timezone"><Input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} /></Field>
          <Field label="Start Date"><Input required type="date" value={form.date_start} onChange={(e) => setForm({ ...form, date_start: e.target.value })} /></Field>
          <Field label="End Date"><Input required type="date" value={form.date_end} onChange={(e) => setForm({ ...form, date_end: e.target.value })} /></Field>
          <Field label="Starting Balance"><Input type="number" value={form.starting_balance} onChange={(e) => setForm({ ...form, starting_balance: Number(e.target.value) })} /></Field>
          <Field label="Risk % / Trade"><Input type="number" step="0.1" value={form.risk_pct_per_trade} onChange={(e) => setForm({ ...form, risk_pct_per_trade: Number(e.target.value) })} /></Field>
          <Field label="Commission / Trade"><Input type="number" step="0.01" value={form.commission_per_trade} onChange={(e) => setForm({ ...form, commission_per_trade: Number(e.target.value) })} /></Field>
          <Field label="Slippage %"><Input type="number" step="0.01" value={form.slippage_pct} onChange={(e) => setForm({ ...form, slippage_pct: Number(e.target.value) })} /></Field>
          <Field label="Max Trades / Day"><Input type="number" value={form.max_trades_per_day} onChange={(e) => setForm({ ...form, max_trades_per_day: e.target.value })} placeholder="unlimited" /></Field>
          <div className="col-span-full">
            {error && <ErrorNote message={error} />}
            <Button type="submit" disabled={submitting || isActive} className="mt-2">
              {(submitting || isActive) && <Spinner />} Run backtest
            </Button>
          </div>
        </form>
      )}

      {!backtests && <Spinner />}
      {backtests && backtests.length === 0 && <EmptyState title="No backtests yet for this version." />}
      {backtests && backtests.length > 0 && (
        <div className="divide-y divide-base-800">
          {backtests.map((bt) => (
            <Link key={bt.id} href={`/backtests/${bt.id}`} className="flex items-center justify-between py-3 hover:bg-base-850">
              <div>
                <p className="text-sm text-slate-200">
                  {bt.symbol} &middot; {new Date(bt.date_start).toLocaleDateString()}–{new Date(bt.date_end).toLocaleDateString()}
                </p>
                <p className="text-xs text-slate-500">
                  {bt.metrics ? `${bt.metrics.num_trades} trades · Net ${bt.metrics.net_profit.toFixed(0)}` : "No metrics yet"}
                </p>
              </div>
              <Badge tone={STATUS_TONE[bt.status]}>{bt.status}</Badge>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
    </div>
  );
}
