"use client";

import { useEffect, useRef, useState } from "react";
import { useApi } from "./api";
import type { Job } from "./types";

/** Polls `GET /jobs/{id}` every `intervalMs` until the job reaches SUCCESS
 * or FAILED. This is the frontend half of Module: Background Job System —
 * every long-running action (ingestion, extraction, backtesting) returns a
 * `Job` immediately and progress is shown by polling, never by blocking
 * the request or faking a progress bar. */
export function useJobPolling(intervalMs = 1500) {
  const api = useApi();
  const [job, setJob] = useState<Job | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stop() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  function track(initialJob: Job) {
    stop();
    setJob(initialJob);
    if (initialJob.status === "SUCCESS" || initialJob.status === "FAILED") return;
    timerRef.current = setInterval(async () => {
      try {
        const updated = await api.getJob(initialJob.id);
        setJob(updated);
        if (updated.status === "SUCCESS" || updated.status === "FAILED") stop();
      } catch {
        stop();
      }
    }, intervalMs);
  }

  useEffect(() => stop, []);

  return { job, track, isActive: job !== null && job.status !== "SUCCESS" && job.status !== "FAILED" };
}
