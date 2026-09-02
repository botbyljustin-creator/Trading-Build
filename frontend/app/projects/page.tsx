"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useCurrentProject } from "@/lib/useCurrentProject";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Spinner";
import type { Project } from "@/lib/types";
import { useRouter } from "next/navigation";

export default function ProjectsPage() {
  const api = useApi();
  const router = useRouter();
  const { projectId, setProjectId } = useCurrentProject();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setProjects(await api.listProjects());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects.");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const project = await api.createProject({ name, description: description || undefined });
      setName("");
      setDescription("");
      await refresh();
      setProjectId(project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this project and everything in it? This cannot be undone.")) return;
    await api.deleteProject(id);
    if (projectId === id) setProjectId(null);
    await refresh();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Projects</h1>

      <Card>
        <CardHeader title="New project" subtitle="A project holds the sources, rules, and strategies for one research effort." />
        <form onSubmit={handleCreate} className="space-y-3">
          <div>
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Morning Reversal Research" required />
          </div>
          <div>
            <Label>Description (optional)</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          {error && <ErrorNote message={error} />}
          <Button type="submit" disabled={creating}>
            {creating && <Spinner />} Create Project
          </Button>
        </form>
      </Card>

      <Card>
        <CardHeader title="Your projects" />
        {!projects && <Spinner />}
        {projects && projects.length === 0 && (
          <EmptyState title="No projects yet" description="Create one above to get started." />
        )}
        {projects && projects.length > 0 && (
          <div className="divide-y divide-base-800">
            {projects.map((p) => (
              <div key={p.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-slate-200">{p.name}</p>
                  {p.description && <p className="text-xs text-slate-500">{p.description}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setProjectId(p.id);
                      router.push("/sources");
                    }}
                  >
                    Open
                  </Button>
                  <Button variant="danger" onClick={() => handleDelete(p.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
