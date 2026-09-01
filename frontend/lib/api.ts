// Thin server-side client for the US100 COMMAND backend.
//
// Server Components use INTERNAL_API_URL (the Docker-network hostname,
// e.g. http://backend:8000) so backend traffic never needs to leave the
// compose network. Client Components (added from Phase 6 onward, for
// polling/live updates) use NEXT_PUBLIC_API_URL instead, which points at
// the browser-reachable address (e.g. http://localhost:8000). Never mix
// the two: a Client Component calling INTERNAL_API_URL would try to
// resolve the Docker-internal hostname from the user's browser and fail.

export interface ComponentHealth {
  status: "ok" | "error";
  error: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app_name: string;
  app_version: string;
  app_env: string;
  timestamp: string;
  components: Record<string, ComponentHealth>;
}

function internalApiUrl(): string {
  return process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

/**
 * Fetch backend health. Never throws — a network failure is reported as an
 * "unreachable" health payload so the dashboard can render a clear
 * DATA STALE / backend-down state instead of crashing the page. This
 * mirrors the backend's own fail-safe health-check design.
 */
export async function getBackendHealth(): Promise<HealthResponse | { unreachable: true; error: string }> {
  try {
    const res = await fetch(`${internalApiUrl()}/api/v1/health`, { cache: "no-store" });
    if (!res.ok) {
      return { unreachable: true, error: `backend responded with HTTP ${res.status}` };
    }
    return (await res.json()) as HealthResponse;
  } catch (err) {
    return { unreachable: true, error: err instanceof Error ? err.message : "unknown error" };
  }
}
