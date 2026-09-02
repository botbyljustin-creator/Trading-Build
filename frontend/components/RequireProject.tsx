"use client";

import Link from "next/link";
import { useCurrentProject } from "@/lib/useCurrentProject";
import { EmptyState } from "./ui/Spinner";
import { Button } from "./ui/Button";

export function RequireProject({ children }: { children: (projectId: string) => React.ReactNode }) {
  const { projectId, hydrated } = useCurrentProject();

  if (!hydrated) return null;

  if (!projectId) {
    return (
      <EmptyState
        title="No project selected"
        description="Select a project from the header, or create a new one."
      >
        <div className="mt-4">
          <Link href="/projects">
            <Button>Go to Projects</Button>
          </Link>
        </div>
      </EmptyState>
    );
  }

  return <>{children(projectId)}</>;
}
