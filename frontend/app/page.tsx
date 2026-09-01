import { getBackendHealth } from "@/lib/api";

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-1 font-mono text-xs uppercase tracking-wider ${
        ok ? "bg-accent-long/10 text-accent-long" : "bg-accent-short/10 text-accent-short"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-accent-long" : "bg-accent-short"}`} />
      {label}
    </span>
  );
}

export default async function CommandCenterPage() {
  const health = await getBackendHealth();
  const backendReachable = !("unreachable" in health);

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-base-700 bg-base-900 p-6">
        <div className="flex items-center justify-between">
          <h1 className="font-mono text-lg font-semibold text-slate-100">System Health</h1>
          <StatusPill ok={backendReachable} label={backendReachable ? "backend up" : "backend down"} />
        </div>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          Phase 1 wires the dashboard shell to the backend health endpoint end to end. Market
          data, scanner, signals, risk, and the full command center layout arrive in later
          phases — see <code className="font-mono text-slate-300">IMPLEMENTATION_PLAN.md</code>.
        </p>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {backendReachable ? (
            <>
              <InfoTile label="App" value={`${health.app_name} v${health.app_version}`} />
              <InfoTile label="Environment" value={health.app_env} />
              <InfoTile label="Overall Status" value={health.status.toUpperCase()} />
              {Object.entries(health.components).map(([name, component]) => (
                <InfoTile
                  key={name}
                  label={name}
                  value={component.status.toUpperCase()}
                  error={component.error ?? undefined}
                />
              ))}
            </>
          ) : (
            <InfoTile label="Backend" value="UNREACHABLE" error={health.error} />
          )}
        </div>
      </section>

      <section className="rounded-lg border border-dashed border-base-700 bg-base-900/50 p-6 text-sm text-slate-500">
        <p className="font-mono uppercase tracking-wider text-slate-400">Coming next</p>
        <p className="mt-2">
          Market data feed, live candles, indicator state, scanner output, strategy signals,
          AI analysis, trade planning, risk verdicts, and paper trading will populate this
          Command Center in Phases 2&ndash;9. Simulated data will always be clearly labeled
          <span className="mx-1 rounded bg-accent-warn/10 px-1.5 py-0.5 font-mono text-xs text-accent-warn">
            SIMULATED DATA
          </span>
          and never presented as live market data.
        </p>
      </section>
    </div>
  );
}

function InfoTile({ label, value, error }: { label: string; value: string; error?: string }) {
  return (
    <div className="rounded border border-base-700 bg-base-850 p-4">
      <p className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-sm text-slate-200">{value}</p>
      {error && <p className="mt-1 text-xs text-accent-short">{error}</p>}
    </div>
  );
}
