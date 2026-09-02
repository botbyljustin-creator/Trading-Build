"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "@/lib/api";
import { useJobPolling } from "@/lib/useJobPolling";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge, JobStatusBadge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import type { Backtest, OptimizationRun } from "@/lib/types";

export default function BacktestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const api = useApi();
  const [backtest, setBacktest] = useState<Backtest | null>(null);
  const [robustness, setRobustness] = useState<OptimizationRun[]>([]);
  const { job: robustnessJob, track: trackRobustness, isActive: robustnessRunning } = useJobPolling();
  const { job: reportJob, track: trackReport, isActive: reportRunning } = useJobPolling();
  const [reportId, setReportId] = useState<string | null>(null);

  async function refresh() {
    const bt = await api.getBacktest(id);
    setBacktest(bt);
    setRobustness(await api.listRobustnessRuns(id).catch(() => []));
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(() => {
      if (backtest?.status === "PENDING" || backtest?.status === "RUNNING") refresh();
    }, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (robustnessJob?.status === "SUCCESS") refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [robustnessJob?.status]);

  useEffect(() => {
    if (reportJob?.status === "SUCCESS") {
      setReportId((reportJob.result_ref?.report_id as string) ?? null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportJob?.status]);

  if (!backtest) return <Spinner />;

  const metrics = backtest.metrics;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">
            {backtest.symbol} backtest
          </h1>
          <p className="text-xs text-slate-500">
            {backtest.provider} &middot; {backtest.timezone} &middot; {backtest.asset_type} &middot;{" "}
            {new Date(backtest.date_start).toLocaleDateString()}–{new Date(backtest.date_end).toLocaleDateString()}
          </p>
        </div>
        <Badge tone={backtest.status === "COMPLETE" ? "success" : backtest.status === "FAILED" ? "danger" : "info"}>
          {backtest.status}
        </Badge>
      </div>

      {backtest.status === "FAILED" && <EmptyState title="Backtest failed" description={backtest.error_message ?? undefined} />}
      {(backtest.status === "PENDING" || backtest.status === "RUNNING") && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Running backtest...
        </div>
      )}

      {metrics && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="Net Return" value={`${metrics.total_return_pct.toFixed(2)}%`} tone={metrics.total_return_pct >= 0 ? "success" : "danger"} />
            <MetricCard label="Max Drawdown" value={`${metrics.max_drawdown_pct.toFixed(2)}%`} tone="danger" />
            <MetricCard label="Profit Factor" value={metrics.profit_factor != null ? metrics.profit_factor.toFixed(2) : "—"} />
            <MetricCard label="Win Rate" value={`${metrics.win_rate_pct.toFixed(1)}%`} />
            <MetricCard label="Trades" value={metrics.num_trades.toString()} />
            <MetricCard label="Sharpe" value={metrics.sharpe_ratio != null ? metrics.sharpe_ratio.toFixed(2) : "—"} />
          </div>

          <Card>
            <CardHeader title="Equity Curve" />
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={metrics.equity_curve}>
                <defs>
                  <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#16c784" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#16c784" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1c2430" />
                <XAxis dataKey="timestamp" tick={false} stroke="#3d4a5e" />
                <YAxis stroke="#3d4a5e" tick={{ fontSize: 11 }} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#0f141c", border: "1px solid #1c2430", fontSize: 12 }} />
                <Area type="monotone" dataKey="equity" stroke="#16c784" fill="url(#equityFill)" strokeWidth={1.5} />
              </AreaChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <CardHeader title="Drawdown" />
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={metrics.drawdown_curve}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1c2430" />
                <XAxis dataKey="timestamp" tick={false} stroke="#3d4a5e" />
                <YAxis stroke="#3d4a5e" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#0f141c", border: "1px solid #1c2430", fontSize: 12 }} />
                <Line type="monotone" dataKey="drawdown_pct" stroke="#ef4c54" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader title="Monthly Returns" />
              <div className="max-h-56 overflow-y-auto text-sm">
                {Object.entries(metrics.monthly_returns).map(([month, pct]) => (
                  <div key={month} className="flex justify-between border-b border-base-800 py-1">
                    <span className="text-slate-400">{month}</span>
                    <span className={pct >= 0 ? "text-accent-long" : "text-accent-short"}>{pct.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </Card>
            <Card>
              <CardHeader title="Long vs Short" />
              <div className="space-y-2 text-sm">
                <DirectionRow label="Long" stats={metrics.long_stats} />
                <DirectionRow label="Short" stats={metrics.short_stats} />
              </div>
            </Card>
          </div>

          <Card>
            <CardHeader title="Trade List" subtitle={`${backtest.trades.length} trades`} />
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-base-900 text-slate-500">
                  <tr>
                    <th className="py-1 pr-2">Direction</th>
                    <th className="py-1 pr-2">Entry</th>
                    <th className="py-1 pr-2">Exit</th>
                    <th className="py-1 pr-2">PnL</th>
                    <th className="py-1 pr-2">R</th>
                    <th className="py-1 pr-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.trades.map((t, i) => (
                    <tr key={i} className="border-t border-base-800">
                      <td className="py-1 pr-2">
                        <Badge tone={t.direction === "LONG" ? "success" : "info"}>{t.direction}</Badge>
                      </td>
                      <td className="py-1 pr-2 text-slate-400">{new Date(t.entry_time).toLocaleString()}</td>
                      <td className="py-1 pr-2 text-slate-400">{new Date(t.exit_time).toLocaleString()}</td>
                      <td className={`py-1 pr-2 ${t.pnl >= 0 ? "text-accent-long" : "text-accent-short"}`}>{t.pnl.toFixed(2)}</td>
                      <td className="py-1 pr-2">{t.r_multiple.toFixed(2)}R</td>
                      <td className="py-1 pr-2 text-slate-500">{t.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {backtest.assumptions_notes && (
            <Card>
              <CardHeader title="Backtest Notes & Assumptions" subtitle="Unrealistic or unresolved assumptions in this run, labeled explicitly." />
              <pre className="whitespace-pre-wrap text-xs text-accent-warn">{backtest.assumptions_notes}</pre>
            </Card>
          )}

          <Card>
            <CardHeader
              title="Robustness"
              subtitle="In-sample vs out-of-sample split and overfitting risk assessment."
            />
            <div className="mb-3 flex justify-end">
              <Button
                onClick={async () => {
                  const j = await api.runRobustness(id);
                  trackRobustness(j);
                }}
                disabled={robustnessRunning}
              >
                {robustnessRunning && <Spinner />} Run robustness test
              </Button>
            </div>
            {robustness.length === 0 && <EmptyState title="No robustness tests run yet." />}
            {robustness.map((r) => (
              <div key={r.id} className="mb-2 rounded-md border border-base-700 bg-base-850 p-3 text-xs">
                <div className="mb-1 flex items-center gap-2">
                  <span className="font-medium text-slate-300">{r.run_type}</span>
                  {r.overfitting_risk && (
                    <Badge tone={r.overfitting_risk === "LOW" ? "success" : r.overfitting_risk === "MEDIUM" ? "warn" : "danger"}>
                      {r.overfitting_risk} overfitting risk
                    </Badge>
                  )}
                </div>
                {r.overfitting_reasons?.map((reason, i) => (
                  <p key={i} className="text-slate-500">
                    &bull; {reason}
                  </p>
                ))}
              </div>
            ))}
          </Card>

          <Card>
            <CardHeader title="Strategy Report" subtitle="Full traceability report: rules, contradictions, backtest results, limitations." />
            <div className="flex items-center gap-2">
              {reportJob && <JobStatusBadge status={reportJob.status} />}
              <Button
                onClick={async () => {
                  const j = await api.generateReport(backtest.strategy_version_id, backtest.id);
                  trackReport(j);
                }}
                disabled={reportRunning}
              >
                {reportRunning && <Spinner />} Generate report
              </Button>
              {reportId && (
                <a href={`/reports/view/${reportId}`} className="text-xs text-accent-info hover:underline">
                  View report &rarr;
                </a>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: string; tone?: "success" | "danger" }) {
  return (
    <div className="rounded-lg border border-base-700 bg-base-900 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${tone === "success" ? "text-accent-long" : tone === "danger" ? "text-accent-short" : "text-slate-100"}`}>
        {value}
      </p>
    </div>
  );
}

function DirectionRow({ label, stats }: { label: string; stats: { num_trades: number; win_rate_pct: number; net_profit: number } }) {
  return (
    <div className="flex items-center justify-between border-b border-base-800 py-1">
      <span className="text-slate-400">{label}</span>
      <span className="text-slate-300">
        {stats.num_trades} trades &middot; {stats.win_rate_pct.toFixed(1)}% win &middot; Net {stats.net_profit.toFixed(0)}
      </span>
    </div>
  );
}
