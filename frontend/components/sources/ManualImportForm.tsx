"use client";

import { useState } from "react";
import { useApi } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { ErrorNote, Spinner } from "@/components/ui/Spinner";

/** Lets a user paste a transcript fetched outside StrategyForge AI — the
 * workaround for environments that can't reach youtube.com directly (see
 * README.md and CURRENT_STATE.md). Accepts the exact JSON shape
 * `youtube_transcript_api.YouTubeTranscriptApi.get_transcript()` returns,
 * so no reformatting is needed. */
export function ManualImportForm({ projectId, onImported }: { projectId: string; onImported: () => void }) {
  const api = useApi();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [creatorName, setCreatorName] = useState("");
  const [seriesName, setSeriesName] = useState("");
  const [segmentsJson, setSegmentsJson] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    let segments;
    try {
      segments = JSON.parse(segmentsJson);
      if (!Array.isArray(segments) || segments.length === 0) throw new Error("empty");
    } catch {
      setError(
        'Segments must be a JSON array like [{"start": 0.0, "duration": 5.0, "text": "..."}, ...] — exactly what youtube_transcript_api.get_transcript() returns.',
      );
      return;
    }
    setSubmitting(true);
    try {
      await api.importManualVideo(projectId, {
        url,
        title,
        creator_name: creatorName,
        series_name: seriesName || undefined,
        segments,
      });
      setUrl("");
      setTitle("");
      setSeriesName("");
      setSegmentsJson("");
      onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <p className="text-xs text-slate-500">
        On a machine that can reach YouTube: <code className="text-slate-300">pip install youtube-transcript-api</code>,
        then <code className="text-slate-300">python -c &quot;from youtube_transcript_api import YouTubeTranscriptApi as A; import json; json.dump(A.get_transcript(&apos;VIDEO_ID&apos;), open(&apos;t.json&apos;,&apos;w&apos;))&quot;</code>,
        then paste the contents of <code className="text-slate-300">t.json</code> below. This never fabricates
        transcript text — it only stores what you provide.
      </p>
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <Label>Video URL</Label>
          <Input required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=..." />
        </div>
        <div>
          <Label>Title</Label>
          <Input required value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <Label>Creator</Label>
          <Input required value={creatorName} onChange={(e) => setCreatorName(e.target.value)} placeholder="e.g. Inner Circle Trader" />
        </div>
        <div className="col-span-2">
          <Label>Series / Mentorship (optional — leave blank for a standalone video)</Label>
          <Input value={seriesName} onChange={(e) => setSeriesName(e.target.value)} placeholder="e.g. 2022 Mentorship" />
        </div>
        <div className="col-span-2">
          <Label>Transcript segments (JSON)</Label>
          <Textarea
            required
            rows={6}
            value={segmentsJson}
            onChange={(e) => setSegmentsJson(e.target.value)}
            placeholder='[{"start": 0.0, "duration": 4.2, "text": "..."}, ...]'
            className="font-mono text-xs"
          />
        </div>
      </div>
      {error && <ErrorNote message={error} />}
      <Button type="submit" disabled={submitting}>
        {submitting && <Spinner />} Import transcript
      </Button>
    </form>
  );
}
