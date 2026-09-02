"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireProject } from "@/components/RequireProject";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import type { Backtest, Strategy } from "@/lib/types";

interface Row {
  backtest: Backtest;
  strategyName: string;
  versionLabel: string | null;
}

const STATUS_TONE: Record<string, "neutral" | "success" | "danger" | "warn" | "info"> = {
  PENDING: "neutral",
  RUNNING: "info",
  COMPLETE: "success",
  FAILED: "danger",
};

export default function BacktestsPage() {
  return <RequireProject>{(projectId) => <BacktestsForProject projectId={projectId} />}</RequireProject>;
}

function BacktestsForProject({ projectId }: { projectId: string }) {
  const api = useApi();
  const [rows, setRows] = useState<Row[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const strategies: Strategy[] = await api.listStrategies(projectId);
      const collected: Row[] = [];
      for (const strategy of strategies) {
        for (const version of strategy.versions) {
          const backtests = await api.listBacktests(version.id).catch(() => []);
          for (const bt of backtests) {
            collected.push({ backtest: bt, strategyName: strategy.name, versionLabel: version.label });
          }
        }
      }
      collected.sort((a, b) => (a.backtest.created_at < b.backtest.created_at ? 1 : -1));
      if (!cancelled) setRows(collected);
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Backtests</h1>
      <Card>
        <CardHeader title="All backtests in this project" />
        {!rows && <Spinner />}
        {rows && rows.length === 0 && (
          <EmptyState title="No backtests yet" description="Run one from a strategy version's Backtests tab." />
        )}
        {rows && rows.length > 0 && (
          <div className="divide-y divide-base-800">
            {rows.map(({ backtest, strategyName, versionLabel }) => (
              <Link key={backtest.id} href={`/backtests/${backtest.id}`} className="flex items-center justify-between py-3 hover:bg-base-850">
                <div>
                  <p className="text-sm text-slate-200">
                    {strategyName} &middot; {versionLabel} &middot; {backtest.symbol}
                  </p>
                  <p className="text-xs text-slate-500">
                    {backtest.metrics
                      ? `${backtest.metrics.num_trades} trades · Net ${backtest.metrics.net_profit.toFixed(0)} · PF ${backtest.metrics.profit_factor?.toFixed(2) ?? "—"}`
                      : "No metrics yet"}
                  </p>
                </div>
                <Badge tone={STATUS_TONE[backtest.status]}>{backtest.status}</Badge>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
