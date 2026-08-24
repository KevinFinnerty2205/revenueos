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
    title: "Move your first customer conversation forward",
    body: "RevenueOS helps you prepare, capture what happened, review the evidence and keep the next step clear.",
    href: null,
    action: "Show me how",
  },
  {
    title: "Use authorised information",
    body: "Review this private-beta notice before you add customer information. You stay in control of what enters the workspace.",
    href: null,
    action: "Notice reviewed",
  },
  {
    title: "Start with a deal",
    body: "Create your first opportunity, or open the seeded example if your beta operator has prepared one. Add only the context needed to make the next conversation useful.",
    href: "/opportunities/new",
    action: "I have a deal to work on",
  },
  {
    title: "Plan the next interaction",
    body: "Add the next meeting, call or in-person interaction from the deal. RevenueOS will keep preparation and capture in the same customer journey.",
    href: "/interactions/new",
    action: "I know the next interaction",
  },
  {
    title: "Use one simple loop",
    body: "Prepare before the interaction, use Companion when it starts, capture the outcome afterwards, then review the next action on the deal. Home brings the work that needs attention back to you.",
    href: "/dashboard",
    action: "Go to Home",
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
          You can revisit this guide from its direct link at any time. RevenueOS
          suggestions still need your review before anything changes.
        </p>
        <Link className="primary-button mt-6" href="/dashboard">
          Go to Home
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
            {index === 2
              ? "Add an opportunity"
              : index === 3
                ? "Add an interaction"
                : "Open Home"}
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
