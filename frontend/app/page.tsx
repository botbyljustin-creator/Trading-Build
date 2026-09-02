"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import type { Project } from "@/lib/types";

interface ProjectStats {
  project: Project;
  videoCount: number;
  ruleCount: number;
  strategyCount: number;
  backtestCount: number;
  bestProfitFactor: number | null;
  lowestDrawdown: number | null;
}

export default function DashboardPage() {
  const api = useApi();
  const [stats, setStats] = useState<ProjectStats[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const projects = await api.listProjects();
        const results: ProjectStats[] = [];
        for (const project of projects) {
          const [sources, rules, strategies] = await Promise.all([
            api.listSources(project.id).catch(() => []),
            api.listRules(project.id).catch(() => []),
            api.listStrategies(project.id).catch(() => []),
          ]);
          const videoCounts = await Promise.all(
            sources.map((s) => api.listSourceVideos(s.id).catch(() => [])),
          );
          const videoCount = videoCounts.reduce((sum, v) => sum + v.length, 0);

          let backtestCount = 0;
          let bestProfitFactor: number | null = null;
          let lowestDrawdown: number | null = null;
          for (const strategy of strategies) {
            for (const version of strategy.versions) {
              const backtests = await api.listBacktests(version.id).catch(() => []);
              backtestCount += backtests.length;
              for (const bt of backtests) {
                if (bt.metrics?.profit_factor != null) {
                  bestProfitFactor = Math.max(bestProfitFactor ?? -Infinity, bt.metrics.profit_factor);
                }
                if (bt.metrics?.max_drawdown_pct != null) {
                  lowestDrawdown =
                    lowestDrawdown === null
                      ? bt.metrics.max_drawdown_pct
                      : Math.max(lowestDrawdown, bt.metrics.max_drawdown_pct);
                }
              }
            }
          }

          results.push({
            project,
            videoCount,
            ruleCount: rules.length,
            strategyCount: strategies.length,
            backtestCount,
            bestProfitFactor,
            lowestDrawdown,
          });
        }
        if (!cancelled) setStats(results);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load dashboard.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totals = stats?.reduce(
    (acc, s) => ({
      activeStrategies: acc.activeStrategies + s.strategyCount,
      videosProcessed: acc.videosProcessed + s.videoCount,
      rulesExtracted: acc.rulesExtracted + s.ruleCount,
      backtestsCompleted: acc.backtestsCompleted + s.backtestCount,
      bestProfitFactor:
        s.bestProfitFactor != null ? Math.max(acc.bestProfitFactor ?? -Infinity, s.bestProfitFactor) : acc.bestProfitFactor,
      lowestDrawdown:
        s.lowestDrawdown != null
          ? acc.lowestDrawdown === null
            ? s.lowestDrawdown
            : Math.max(acc.lowestDrawdown, s.lowestDrawdown)
          : acc.lowestDrawdown,
    }),
    {
      activeStrategies: 0,
      videosProcessed: 0,
      rulesExtracted: 0,
      backtestsCompleted: 0,
      bestProfitFactor: null as number | null,
      lowestDrawdown: null as number | null,
    },
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-500">
            StrategyForge AI turns educational trading content into structured, testable trading systems.
          </p>
        </div>
        <Link href="/projects">
          <Button>New Project</Button>
        </Link>
      </div>

      {error && <p className="text-sm text-accent-short">{error}</p>}

      {!stats && !error && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading dashboard...
        </div>
      )}

      {stats && stats.length === 0 && (
        <EmptyState
          title="No projects yet"
          description="Create your first project and paste a YouTube video, playlist, or channel URL to get started."
        />
      )}

      {totals && stats && stats.length > 0 && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
          <StatTile label="Active Strategies" value={totals.activeStrategies} />
          <StatTile label="Videos Processed" value={totals.videosProcessed} />
          <StatTile label="Rules Extracted" value={totals.rulesExtracted} />
          <StatTile label="Backtests Completed" value={totals.backtestsCompleted} />
          <StatTile
            label="Best Profit Factor"
            value={totals.bestProfitFactor != null ? totals.bestProfitFactor.toFixed(2) : "—"}
          />
          <StatTile
            label="Lowest Drawdown"
            value={totals.lowestDrawdown != null ? `${totals.lowestDrawdown.toFixed(1)}%` : "—"}
          />
        </div>
      )}

      {stats && stats.length > 0 && (
        <Card>
          <CardHeader title="Projects" subtitle="Click through to manage sources, rules, and strategies." />
          <div className="divide-y divide-base-800">
            {stats.map((s) => (
              <Link
                key={s.project.id}
                href="/sources"
                onClick={() => window.localStorage.setItem("strategyforge.currentProjectId", s.project.id)}
                className="flex items-center justify-between py-3 text-sm hover:bg-base-850"
              >
                <div>
                  <p className="font-medium text-slate-200">{s.project.name}</p>
                  <p className="text-xs text-slate-500">{s.project.description || "No description"}</p>
                </div>
                <div className="flex gap-4 text-xs text-slate-500">
                  <span>{s.videoCount} videos</span>
                  <span>{s.ruleCount} rules</span>
                  <span>{s.strategyCount} strategies</span>
                  <span>{s.backtestCount} backtests</span>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-100">{value}</p>
    </div>
  );
}
