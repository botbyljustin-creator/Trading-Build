import type { ReactNode } from "react";
import clsx from "clsx";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("rounded-lg border border-base-700 bg-base-900 p-5", className)}>{children}</div>;
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-sm font-semibold tracking-wide text-slate-100">{title}</h2>
        {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
