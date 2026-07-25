"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DataNoticeCard } from "@/components/data-notice-card";
import { apiRequest } from "@/lib/api";

interface OnboardingState {
  currentStep: number;
  skipped: boolean;
  completed: boolean;
  completedAt: string | null;
}

const steps = [
  {
    title: "Welcome to Sales Brain",
    body: "Use RevenueOS to turn deliberately supplied meeting text into reviewable sales intelligence.",
    href: null,
    action: "Start safely",
  },
  {
    title: "Review the data notice",
    body: "Acknowledge the notice below before adding a transcript or requesting intelligence.",
    href: null,
    action: "Notice acknowledged",
  },
  {
    title: "Add a company",
    body: "Create the organisation you are selling to, or ask your operator to seed the synthetic demo dataset.",
    href: "/companies/new",
    action: "Continue",
  },
  {
    title: "Create an opportunity",
    body: "Connect the commercial context to the company.",
    href: "/opportunities/new",
    action: "Continue",
  },
  {
    title: "Add a meeting",
    body: "Create a meeting and associate it with the opportunity.",
    href: "/meetings/new",
    action: "Continue",
  },
  {
    title: "Add safe transcript text",
    body: "Paste only content you are authorised to process. Synthetic demo text is safest for the beta.",
    href: "/meetings",
    action: "Continue",
  },
  {
    title: "Generate Meeting Intelligence",
    body: "Use the synthetic demo path for a deterministic demonstration that stays inside RevenueOS.",
    href: "/meetings",
    action: "Continue",
  },
  {
    title: "Open Opportunity Workspace",
    body: "Review the linked meetings, evidence and next action in one place.",
    href: "/opportunities",
    action: "Continue",
  },
  {
    title: "Review Revenue Brain",
    body: "After two complete demo meetings, inspect the explainable change timeline.",
    href: "/companies",
    action: "Finish onboarding",
  },
] as const;

export function BetaOnboarding() {
  const [state, setState] = useState<OnboardingState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiRequest<OnboardingState>("/api/v1/beta/onboarding")
      .then(setState)
      .catch((reason: unknown) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "Onboarding could not be loaded.",
        ),
      );
  }, []);

  async function update(
    action: "advance" | "skip" | "complete",
    currentStep?: number,
  ) {
    setSaving(true);
    setError(null);
    try {
      const next = await apiRequest<OnboardingState>(
        "/api/v1/beta/onboarding",
        {
          method: "PATCH",
          body: JSON.stringify({ action, currentStep }),
        },
      );
      setState(next);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Onboarding progress could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (error && !state)
    return (
      <p role="alert" className="rounded-2xl bg-rose-50 p-4 text-rose-900">
        {error}
      </p>
    );
  if (!state)
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading onboarding…
      </p>
    );
  if (state.completed) {
    return (
      <section
        className="form-card"
        aria-labelledby="onboarding-complete-title"
      >
        <h2 id="onboarding-complete-title" className="text-2xl font-semibold">
          Your workspace is ready
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          You can revisit this guide at any time. Generated intelligence still
          needs human review.
        </p>
        <Link className="primary-button mt-6" href="/dashboard">
          Open dashboard
        </Link>
      </section>
    );
  }

  const index = Math.min(state.currentStep, steps.length - 1);
  const step = steps[index];
  return (
    <div className="space-y-6">
      <div
        aria-label={`Onboarding step ${index + 1} of ${steps.length}`}
        className="h-2 overflow-hidden rounded-full bg-slate-200"
      >
        <div
          className="h-full bg-teal-700"
          style={{ width: `${((index + 1) / steps.length) * 100}%` }}
        />
      </div>
      <section className="form-card" aria-labelledby="onboarding-step-title">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
          Step {index + 1} of {steps.length}
        </p>
        <h2 id="onboarding-step-title" className="mt-2 text-2xl font-semibold">
          {step.title}
        </h2>
        <p className="mt-3 text-sm leading-7 text-slate-600">{step.body}</p>
        {step.href ? (
          <Link className="secondary-button mt-5" href={step.href}>
            Open this step
          </Link>
        ) : null}
      </section>
      {index === 1 ? (
        <DataNoticeCard onAcknowledged={() => void update("advance", 2)} />
      ) : null}
      <div className="flex flex-wrap gap-3">
        {index !== 1 ? (
          <button
            type="button"
            className="primary-button"
            disabled={saving}
            onClick={() =>
              void update(
                index === steps.length - 1 ? "complete" : "advance",
                index + 1,
              )
            }
          >
            {saving ? "Saving…" : step.action}
          </button>
        ) : null}
        <button
          type="button"
          className="secondary-button"
          disabled={saving}
          onClick={() => void update("skip")}
        >
          Skip onboarding
        </button>
      </div>
      {error ? (
        <p
          role="alert"
          className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}
