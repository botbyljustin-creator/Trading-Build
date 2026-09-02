"use client";

import { useAppAuth } from "@/components/AuthProvider";
import type {
  Backtest,
  Concept,
  Contradiction,
  ContradictionResolution,
  GeneratedCodeRow,
  Job,
  OptimizationRun,
  Project,
  Report,
  Rule,
  RuleCategory,
  RuleStatus,
  SourceRecord,
  Strategy,
  StrategyVersion,
  Trade,
  VideoRecord,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

async function request<T>(
  path: string,
  token: string | null,
  init?: { method?: string; body?: unknown },
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${apiBaseUrl()}${path}`, {
    method: init?.method ?? "GET",
    headers,
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Bound API methods for the currently authenticated user (or the dev-mode
 * fixed user when no Clerk key is configured). Every method resolves the
 * auth token fresh on each call rather than caching it. */
export function useApi() {
  const { getToken } = useAppAuth();

  async function call<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
    const token = await getToken();
    return request<T>(path, token, init);
  }

  return {
    // Projects
    listProjects: () => call<Project[]>("/api/v1/projects"),
    createProject: (data: { name: string; description?: string }) =>
      call<Project>("/api/v1/projects", { method: "POST", body: data }),
    getProject: (id: string) => call<Project>(`/api/v1/projects/${id}`),
    updateProject: (id: string, data: { name?: string; description?: string }) =>
      call<Project>(`/api/v1/projects/${id}`, { method: "PATCH", body: data }),
    deleteProject: (id: string) => call<void>(`/api/v1/projects/${id}`, { method: "DELETE" }),

    // Sources / videos
    createSource: (projectId: string, url: string) =>
      call<Job>(`/api/v1/projects/${projectId}/sources`, { method: "POST", body: { url } }),
    confirmSourceCost: (sourceId: string) =>
      call<Job>(`/api/v1/sources/${sourceId}/confirm-cost`, { method: "POST" }),
    listSources: (projectId: string) => call<SourceRecord[]>(`/api/v1/projects/${projectId}/sources`),
    getSource: (id: string) => call<SourceRecord>(`/api/v1/sources/${id}`),
    listSourceVideos: (sourceId: string) => call<VideoRecord[]>(`/api/v1/sources/${sourceId}/videos`),
    getVideo: (id: string) => call<VideoRecord>(`/api/v1/videos/${id}`),

    // Concepts
    extractConcepts: (projectId: string) =>
      call<Job>(`/api/v1/projects/${projectId}/concepts/extract`, { method: "POST" }),
    listConcepts: (projectId: string) => call<Concept[]>(`/api/v1/projects/${projectId}/concepts`),

    // Rules
    extractRules: (projectId: string) =>
      call<Job>(`/api/v1/projects/${projectId}/rules/extract`, { method: "POST" }),
    listRules: (projectId: string, filters?: { status?: RuleStatus; category?: RuleCategory }) => {
      const params = new URLSearchParams();
      if (filters?.status) params.set("rule_status", filters.status);
      if (filters?.category) params.set("category", filters.category);
      const qs = params.toString();
      return call<Rule[]>(`/api/v1/projects/${projectId}/rules${qs ? `?${qs}` : ""}`);
    },
    createManualRule: (
      projectId: string,
      data: { category: RuleCategory; natural_language_rule: string; machine_readable_rule?: Record<string, unknown> },
    ) => call<Rule>(`/api/v1/projects/${projectId}/rules`, { method: "POST", body: data }),
    updateRule: (
      id: string,
      data: { natural_language_rule?: string; machine_readable_rule?: Record<string, unknown>; user_note?: string },
    ) => call<Rule>(`/api/v1/rules/${id}`, { method: "PATCH", body: data }),
    approveRule: (id: string) => call<Rule>(`/api/v1/rules/${id}/approve`, { method: "POST" }),
    rejectRule: (id: string) => call<Rule>(`/api/v1/rules/${id}/reject`, { method: "POST" }),

    // Contradictions
    detectContradictions: (projectId: string) =>
      call<Job>(`/api/v1/projects/${projectId}/contradictions/detect`, { method: "POST" }),
    listContradictions: (projectId: string) =>
      call<Contradiction[]>(`/api/v1/projects/${projectId}/contradictions`),
    resolveContradiction: (id: string, resolution: ContradictionResolution) =>
      call<Contradiction>(`/api/v1/contradictions/${id}/resolve`, { method: "POST", body: { resolution } }),

    // Strategies / versions / code
    createStrategy: (projectId: string, data: { name: string; description?: string }) =>
      call<Strategy>(`/api/v1/projects/${projectId}/strategies`, { method: "POST", body: data }),
    listStrategies: (projectId: string) => call<Strategy[]>(`/api/v1/projects/${projectId}/strategies`),
    getStrategy: (id: string) => call<Strategy>(`/api/v1/strategies/${id}`),
    compileVersion: (strategyId: string, ruleIds: string[]) =>
      call<StrategyVersion>(`/api/v1/strategies/${strategyId}/versions/compile`, {
        method: "POST",
        body: { rule_ids: ruleIds },
      }),
    getVersion: (id: string) => call<StrategyVersion>(`/api/v1/strategy-versions/${id}`),
    getVersionSpec: (id: string) => call<Record<string, unknown>>(`/api/v1/strategy-versions/${id}/spec`),
    compareVersions: (fromId: string, toId: string) =>
      call<{ from_version: number; to_version: number; changes: Record<string, { before: unknown; after: unknown }> }>(
        `/api/v1/strategy-versions/${fromId}/compare/${toId}`,
      ),
    generateCode: (versionId: string) =>
      call<GeneratedCodeRow[]>(`/api/v1/strategy-versions/${versionId}/generate-code`, { method: "POST" }),
    getGeneratedCode: (versionId: string) =>
      call<GeneratedCodeRow[]>(`/api/v1/strategy-versions/${versionId}/code`),

    // Backtests
    createBacktest: (
      versionId: string,
      data: {
        provider: string;
        symbol: string;
        timezone: string;
        exchange_session?: string;
        asset_type: string;
        date_start: string;
        date_end: string;
        starting_balance: number;
        commission_per_trade?: number;
        commission_pct?: number;
        slippage_pct?: number;
        risk_pct_per_trade: number;
        allow_long?: boolean;
        allow_short?: boolean;
        max_trades_per_day?: number;
      },
    ) => call<Job>(`/api/v1/strategy-versions/${versionId}/backtests`, { method: "POST", body: data }),
    listBacktests: (versionId: string) => call<Backtest[]>(`/api/v1/strategy-versions/${versionId}/backtests`),
    getBacktest: (id: string) => call<Backtest>(`/api/v1/backtests/${id}`),
    runRobustness: (id: string) => call<Job>(`/api/v1/backtests/${id}/robustness`, { method: "POST" }),
    listRobustnessRuns: (id: string) => call<OptimizationRun[]>(`/api/v1/backtests/${id}/robustness`),

    // Jobs
    getJob: (id: string) => call<Job>(`/api/v1/jobs/${id}`),
    listJobs: (projectId: string) => call<Job[]>(`/api/v1/projects/${projectId}/jobs`),

    // Reports
    generateReport: (versionId: string, backtestId?: string) =>
      call<Job>(`/api/v1/strategy-versions/${versionId}/reports`, {
        method: "POST",
        body: { backtest_id: backtestId ?? null },
      }),
    getReport: (id: string) => call<Report>(`/api/v1/reports/${id}`),
    listProjectReports: (projectId: string) => call<Report[]>(`/api/v1/projects/${projectId}/reports`),
  };
}

export type { Trade };
