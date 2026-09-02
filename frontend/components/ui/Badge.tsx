import clsx from "clsx";

type Tone = "neutral" | "success" | "danger" | "warn" | "info";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-base-800 text-slate-300",
  success: "bg-accent-long/10 text-accent-long",
  danger: "bg-accent-short/10 text-accent-short",
  warn: "bg-accent-warn/10 text-accent-warn",
  info: "bg-accent-info/10 text-accent-info",
};

export function Badge({ children, tone = "neutral", className }: { children: React.ReactNode; tone?: Tone; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide", toneClasses[tone], className)}>
      {children}
    </span>
  );
}

const RULE_STATUS_TONE: Record<string, Tone> = {
  EXTRACTED: "neutral",
  AMBIGUOUS: "warn",
  CONTRADICTORY: "danger",
  USER_CONFIRMED: "success",
  USER_MODIFIED: "success",
  AI_ASSUMPTION: "warn",
  REJECTED: "danger",
};

export function RuleStatusBadge({ status }: { status: string }) {
  return <Badge tone={RULE_STATUS_TONE[status] ?? "neutral"}>{status.replace(/_/g, " ")}</Badge>;
}

const JOB_STATUS_TONE: Record<string, Tone> = {
  PENDING: "neutral",
  RUNNING: "info",
  SUCCESS: "success",
  FAILED: "danger",
};

export function JobStatusBadge({ status }: { status: string }) {
  return <Badge tone={JOB_STATUS_TONE[status] ?? "neutral"}>{status}</Badge>;
}
