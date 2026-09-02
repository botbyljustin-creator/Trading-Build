"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { UserButton } from "@clerk/nextjs";
import { isClerkConfigured } from "./AuthProvider";
import { useApi } from "@/lib/api";
import { useCurrentProject } from "@/lib/useCurrentProject";
import type { Project } from "@/lib/types";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/sources", label: "Sources" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/strategies", label: "Strategies" },
  { href: "/backtests", label: "Backtests" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
];

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const api = useApi();
  const { projectId, setProjectId, hydrated } = useCurrentProject();
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const first = projects.at(0);
    if (hydrated && !projectId && first) {
      setProjectId(first.id);
    }
  }, [hydrated, projectId, projects, setProjectId]);

  return (
    <header className="border-b border-base-700 bg-base-900">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-3">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-baseline gap-2">
            <span className="text-sm font-bold tracking-widest text-slate-100">STRATEGYFORGE</span>
            <span className="text-[10px] font-medium uppercase tracking-widest text-accent-info">AI</span>
          </Link>
          <select
            value={projectId ?? ""}
            onChange={(e) => {
              setProjectId(e.target.value || null);
              router.refresh();
            }}
            className="rounded-md border border-base-600 bg-base-850 px-2 py-1 text-xs text-slate-300"
          >
            <option value="">No project selected</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <Link href="/projects" className="text-xs text-slate-500 hover:text-slate-300">
            manage projects
          </Link>
        </div>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "rounded-md px-3 py-1.5 text-xs font-medium uppercase tracking-wide transition-colors",
                pathname === item.href ? "bg-base-800 text-slate-100" : "text-slate-500 hover:text-slate-200",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <AuthCorner />
      </div>
    </header>
  );
}

function AuthCorner() {
  if (!isClerkConfigured) {
    return (
      <span className="rounded bg-accent-warn/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-accent-warn">
        Dev mode &middot; no auth configured
      </span>
    );
  }
  return <UserButton afterSignOutUrl="/" />;
}
