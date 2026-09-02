"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import type { Report } from "@/lib/types";

export default function ReportViewPage() {
  const { id } = useParams<{ id: string }>();
  const api = useApi();
  const [report, setReport] = useState<Report | null>(null);

  useEffect(() => {
    api.getReport(id).then(setReport);
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!report) return <Spinner />;
  const c = report.content_json as Record<string, any>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Strategy Report</h1>
        <p className="text-xs text-slate-500">
          Version {c.strategy_version} &middot; Generated {new Date(report.created_at).toLocaleString()}
        </p>
      </div>

      <Card>
        <CardHeader title="Summary" />
        <p className="text-sm text-slate-300">
          Completeness: <Badge tone={c.strategy_summary?.completeness_score_pct === 100 ? "success" : "warn"}>{c.strategy_summary?.completeness_score_pct}%</Badge>
        </p>
      </Card>

      <Section title="Trading Philosophy" data={c.trading_philosophy} />
      <Section title="Setup" data={{ setup: c.setup }} />
      <Section title="Entry" data={c.entry} />
      <Section title="Exit" data={c.exit} />
      <Section title="Risk Management" data={c.risk_management} />
      <Section title="Trade Management" data={c.trade_management} />

      <Card>
        <CardHeader title="No-Trade Conditions" />
        {c.no_trade_conditions?.length ? (
          <ul className="list-inside list-disc text-sm text-slate-300">
            {c.no_trade_conditions.map((n: string, i: number) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-slate-500">None defined.</p>
        )}
      </Card>

      <Card>
        <CardHeader title="Missing Information" />
        {c.missing_information?.length ? (
          <ul className="list-inside list-disc text-sm text-accent-warn">
            {c.missing_information.map((m: string, i: number) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-accent-long">Strategy specification is complete.</p>
        )}
      </Card>

      <Card>
        <CardHeader title="Contradictions" />
        {c.contradictions?.length ? (
          <div className="space-y-2 text-sm">
            {c.contradictions.map((cont: any) => (
              <div key={cont.id} className="rounded border border-base-700 bg-base-850 p-2">
                <Badge tone={cont.resolution === "UNRESOLVED" ? "warn" : "success"}>{cont.resolution}</Badge>
                <p className="mt-1 text-xs text-slate-400">{cont.explanation}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500">None flagged.</p>
        )}
      </Card>

      {c.backtest_configuration && (
        <Card>
          <CardHeader title="Backtest Configuration" />
          <Section title="" data={c.backtest_configuration} bare />
        </Card>
      )}

      {c.backtest_results && (
        <Card>
          <CardHeader title="Backtest Results" />
          <Section title="" data={c.backtest_results} bare />
        </Card>
      )}

      {c.robustness_results && (
        <Card>
          <CardHeader title="Robustness" />
          <div className="text-sm">
            <Badge tone={c.robustness_results.overfitting_risk === "LOW" ? "success" : c.robustness_results.overfitting_risk === "MEDIUM" ? "warn" : "danger"}>
              {c.robustness_results.overfitting_risk} overfitting risk
            </Badge>
            {c.robustness_results.reasons?.map((r: string, i: number) => (
              <p key={i} className="mt-1 text-xs text-slate-400">
                &bull; {r}
              </p>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Limitations" />
        <ul className="list-inside list-disc text-xs text-slate-500">
          {c.limitations?.map((l: string, i: number) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function Section({ title, data, bare }: { title: string; data: Record<string, any> | null; bare?: boolean }) {
  if (!data) return null;
  const body = (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="flex justify-between gap-2 border-b border-base-800 py-1">
          <dt className="text-xs uppercase tracking-wide text-slate-500">{key.replace(/_/g, " ")}</dt>
          <dd className="text-right text-slate-300">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
  if (bare) return body;
  return (
    <Card>
      <CardHeader title={title} />
      {body}
    </Card>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
