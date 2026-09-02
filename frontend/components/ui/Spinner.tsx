import clsx from "clsx";

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={clsx("h-4 w-4 animate-spin text-slate-400", className)} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

export function EmptyState({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-base-700 bg-base-900/50 p-8 text-center">
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {description && <p className="mt-1 text-xs text-slate-500">{description}</p>}
      {children}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-accent-short/30 bg-accent-short/5 px-3 py-2 text-xs text-accent-short">
      {message}
    </div>
  );
}
