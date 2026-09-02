"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "strategyforge.currentProjectId";

/** The project most pages (Sources, Knowledge, Strategies, Backtests,
 * Reports) operate on, persisted per-browser in localStorage. Not shared
 * state across users/devices — purely a UI convenience so switching pages
 * doesn't lose context, matching the top-nav structure in the product
 * spec (a global project switcher rather than every page taking a project
 * id in its URL). */
export function useCurrentProject() {
  const [projectId, setProjectIdState] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setProjectIdState(window.localStorage.getItem(STORAGE_KEY));
    setHydrated(true);
  }, []);

  const setProjectId = useCallback((id: string | null) => {
    setProjectIdState(id);
    if (id) window.localStorage.setItem(STORAGE_KEY, id);
    else window.localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { projectId, setProjectId, hydrated };
}
