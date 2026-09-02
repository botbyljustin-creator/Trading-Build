"use client";

import { useEffect, useState } from "react";
import { RequireProject } from "@/components/RequireProject";
import { useApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Spinner";
import type { SourceRecord, VideoRecord } from "@/lib/types";

export default function SourcesPage() {
  return <RequireProject>{(projectId) => <SourcesForProject projectId={projectId} />}</RequireProject>;
}

const SOURCE_STATUS_TONE: Record<string, "neutral" | "success" | "danger" | "warn" | "info"> = {
  PENDING: "neutral",
  RESOLVING: "info",
  READY: "success",
  FAILED: "danger",
};

function SourcesForProject({ projectId }: { projectId: string }) {
  const api = useApi();
  const [sources, setSources] = useState<SourceRecord[] | null>(null);
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function refresh() {
    try {
      setSources(await api.listSources(projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sources.");
    }
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.createSource(projectId, url.trim());
      setUrl("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add source.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmCost(sourceId: string) {
    await api.confirmSourceCost(sourceId);
    await refresh();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Sources</h1>

      <Card>
        <CardHeader
          title="Add a YouTube source"
          subtitle="Paste a video, playlist, or channel URL. StrategyForge AI will identify the type, fetch metadata, and estimate processing cost before fetching transcripts."
        />
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=... or /playlist?list=... or /@channel"
          />
          <Button type="submit" disabled={submitting}>
            {submitting && <Spinner />} Add
          </Button>
        </form>
        {error && <div className="mt-2"><ErrorNote message={error} /></div>}
      </Card>

      <Card>
        <CardHeader title="Sources" />
        {!sources && <Spinner />}
        {sources && sources.length === 0 && (
          <EmptyState title="No sources yet" description="Add a YouTube URL above to begin ingestion." />
        )}
        {sources && sources.length > 0 && (
          <div className="divide-y divide-base-800">
            {sources.map((s) => (
              <div key={s.id} className="py-3">
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-200">{s.title ?? s.url}</p>
                    <p className="truncate text-xs text-slate-500">{s.url}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge tone="info">{s.source_type.replace("YOUTUBE_", "")}</Badge>
                    <Badge tone={SOURCE_STATUS_TONE[s.status]}>{s.status}</Badge>
                    <Button variant="ghost" onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
                      {expanded === s.id ? "Hide" : "Videos"}
                    </Button>
                  </div>
                </div>
                {s.error_message && <p className="mt-1 text-xs text-accent-short">{s.error_message}</p>}
                {s.status === "READY" && s.estimated_cost_usd != null && (
                  <div className="mt-2 flex items-center gap-3 rounded-md border border-accent-warn/30 bg-accent-warn/5 px-3 py-2 text-xs text-accent-warn">
                    <span>
                      Estimated: {s.estimated_video_count} videos, ~{s.estimated_transcript_tokens?.toLocaleString()} tokens, ~$
                      {s.estimated_cost_usd.toFixed(2)} to process.
                    </span>
                    <Button variant="secondary" onClick={() => handleConfirmCost(s.id)}>
                      Confirm &amp; fetch transcripts
                    </Button>
                  </div>
                )}
                {expanded === s.id && <SourceVideos sourceId={s.id} />}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

const TRANSCRIPT_TONE: Record<string, "neutral" | "success" | "danger" | "warn" | "info"> = {
  PENDING: "neutral",
  AVAILABLE: "success",
  TRANSCRIPT_UNAVAILABLE: "warn",
  FAILED: "danger",
};

function SourceVideos({ sourceId }: { sourceId: string }) {
  const api = useApi();
  const [videos, setVideos] = useState<VideoRecord[] | null>(null);

  useEffect(() => {
    api.listSourceVideos(sourceId).then(setVideos).catch(() => setVideos([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId]);

  if (!videos) return <Spinner className="mt-2" />;
  if (videos.length === 0) return <p className="mt-2 text-xs text-slate-500">No videos resolved yet.</p>;

  return (
    <div className="mt-3 space-y-2 rounded-md bg-base-850 p-3">
      {videos.map((v) => (
        <div key={v.id} className="flex items-center justify-between text-xs">
          <div className="min-w-0">
            <p className="truncate text-slate-300">{v.title}</p>
            <p className="text-slate-600">
              {v.channel_name} &middot; {v.duration_seconds ? `${Math.round(v.duration_seconds / 60)} min` : "duration unknown"}
            </p>
          </div>
          <Badge tone={TRANSCRIPT_TONE[v.transcript_status]}>{v.transcript_status.replace(/_/g, " ")}</Badge>
        </div>
      ))}
    </div>
  );
}
