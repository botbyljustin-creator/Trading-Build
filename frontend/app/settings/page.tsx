"use client";

import { UserProfile } from "@clerk/nextjs";
import { isClerkConfigured } from "@/components/AuthProvider";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Settings</h1>

      <Card>
        <CardHeader title="Account" />
        {isClerkConfigured ? (
          <UserProfile routing="hash" />
        ) : (
          <p className="text-sm text-slate-400">
            No Clerk keys are configured, so the app is running in <Badge tone="warn">dev mode</Badge> as a single
            fixed local user. Set <code className="text-slate-300">CLERK_*</code> variables in your backend{" "}
            <code className="text-slate-300">.env</code> and{" "}
            <code className="text-slate-300">NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> in the frontend to enable real
            accounts. See README.md.
          </p>
        )}
      </Card>

      <Card>
        <CardHeader title="AI providers" subtitle="Configured on the backend, never exposed to the browser." />
        <p className="text-sm text-slate-400">
          Set <code className="text-slate-300">ANTHROPIC_API_KEY</code> and/or{" "}
          <code className="text-slate-300">OPENAI_API_KEY</code> in the backend&apos;s <code className="text-slate-300">.env</code>{" "}
          file. Extraction, contradiction detection, and analyst commentary will fail with a clear error until at
          least one is set — StrategyForge AI never falls back to a fake or hardcoded result.
        </p>
      </Card>

      <Card>
        <CardHeader title="Billing" />
        <p className="text-sm text-slate-400">
          Stripe is <Badge tone="warn">not implemented</Badge> in this build — there is no webhook handler, no
          subscription table, and no plan-gating. Every account currently has unrestricted access. Config variables
          are reserved in <code className="text-slate-300">.env.example</code> for when this is built. See
          ROADMAP.md.
        </p>
      </Card>
    </div>
  );
}
