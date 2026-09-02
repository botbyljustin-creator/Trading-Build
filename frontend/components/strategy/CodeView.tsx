"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { EmptyState, Spinner } from "@/components/ui/Spinner";
import type { CodeLanguage, GeneratedCodeRow } from "@/lib/types";

export function CodeView({ versionId }: { versionId: string }) {
  const api = useApi();
  const [rows, setRows] = useState<GeneratedCodeRow[] | null>(null);
  const [lang, setLang] = useState<CodeLanguage>("PINE");
  const [generating, setGenerating] = useState(false);

  async function refresh() {
    setRows(await api.getGeneratedCode(versionId));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionId]);

  async function handleGenerate() {
    setGenerating(true);
    try {
      await api.generateCode(versionId);
      await refresh();
    } finally {
      setGenerating(false);
    }
  }

  const active = rows?.find((r) => r.language === lang);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          {(["PINE", "PYTHON"] as CodeLanguage[]).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`rounded-md px-3 py-1 text-xs font-medium uppercase ${lang === l ? "bg-base-800 text-slate-100" : "text-slate-500"}`}
            >
              {l}
            </button>
          ))}
        </div>
        <Button onClick={handleGenerate} disabled={generating}>
          {generating && <Spinner />} {rows && rows.length > 0 ? "Regenerate code" : "Generate code"}
        </Button>
      </div>
      {!rows && <Spinner />}
      {rows && rows.length === 0 && (
        <EmptyState title="No code generated yet" description="Click Generate code to render Pine Script and Python from this version's specification." />
      )}
      {active && (
        <pre className="max-h-[32rem] overflow-auto rounded-md border border-base-700 bg-base-950 p-4 text-xs leading-relaxed text-slate-300">
          <code>{active.code}</code>
        </pre>
      )}
    </div>
  );
}
