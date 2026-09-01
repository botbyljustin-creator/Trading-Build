import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "US100 COMMAND",
  description: "AI-assisted NASDAQ-100 / US100 trading analysis platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-base-950 font-sans">
        <header className="flex items-center justify-between border-b border-base-700 bg-base-900 px-6 py-3">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-sm font-semibold tracking-widest text-slate-100">
              US100 COMMAND
            </span>
            <span className="rounded bg-base-800 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-slate-400">
              Phase 1 · Foundations
            </span>
          </div>
          <nav className="font-mono text-xs uppercase tracking-wider text-slate-500">
            command center
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
