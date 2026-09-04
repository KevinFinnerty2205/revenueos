"use client";

import type { CommercialProjection } from "@revenueos/shared";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

const statusLabels: Record<CommercialProjection["status"], string> = {
  trial_active: "Trial active",
  active: "Active",
  grace: "Viewing and export grace",
  expired: "Expired",
  inactive: "Inactive",
  suspended: "Suspended",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function CommercialPlanSettings() {
  const [commercial, setCommercial] = useState<CommercialProjection | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const load = useCallback(async (signal: AbortSignal) => {
    setError(null);
    setCommercial(
      await apiRequest<CommercialProjection>("/api/v1/commercial", { signal }),
    );
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void load(controller.signal).catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Plan information could not be loaded.",
          );
        }
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load, retryKey]);

  if (error && !commercial) {
    return (
      <section className="form-card" aria-labelledby="commercial-plan-title">
        <h2 id="commercial-plan-title" className="form-legend">
          Billing &amp; plan
        </h2>
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {error}
        </p>
        <button
          type="button"
          className="secondary-button mt-4"
          onClick={() => setRetryKey((value) => value + 1)}
        >
          Try again
        </button>
      </section>
    );
  }

  if (!commercial) {
    return (
      <section className="form-card" aria-labelledby="commercial-plan-title">
        <h2 id="commercial-plan-title" className="form-legend">
          Billing &amp; plan
        </h2>
        <p role="status" className="mt-3 text-sm text-slate-600">
          Loading plan information…
        </p>
      </section>
    );
  }

  const limit = commercial.includedUserLimit;
  const isTrial = commercial.status === "trial_active";
  const isGrace = commercial.status === "grace";

  return (
    <section
      className="form-card overflow-hidden"
      aria-labelledby="commercial-plan-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Commercial access
          </p>
          <h2 id="commercial-plan-title" className="form-legend mt-2">
            Billing &amp; plan
          </h2>
        </div>
        <span className="max-w-full rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
          {statusLabels[commercial.status]}
        </span>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Metric label="Current plan" value={commercial.plan.displayName} />
        <Metric
          label="Active users"
          value={`${commercial.activeUserCount} / ${limit ?? "custom"}`}
        />
        <Metric
          label="Billing interval"
          value={commercial.billingInterval ?? "Not recorded"}
        />
      </div>

      <div
        className={`mt-5 rounded-xl border p-4 ${isGrace ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-slate-50"}`}
      >
        <p className="text-sm font-semibold text-slate-950">
          {commercial.message}
        </p>
        {isTrial && commercial.trial.endsAt ? (
          <p className="mt-2 text-sm leading-6 text-slate-700">
            Your 14-day trial ends on {formatDate(commercial.trial.endsAt)}.{" "}
            {commercial.trial.daysRemaining}{" "}
            {commercial.trial.daysRemaining === 1 ? "day" : "days"} remaining.
            No card is required and there is no automatic charge.
          </p>
        ) : null}
        {isGrace && commercial.readAccessEndsAt ? (
          <p className="mt-2 text-sm leading-6 text-slate-700">
            Viewing and export access remains available until{" "}
            {formatDate(commercial.readAccessEndsAt)}. Contact support to resume
            creating or sending new work.
          </p>
        ) : null}
        {commercial.seatLimitStatus === "requires_resolution" ? (
          <p role="alert" className="mt-3 text-sm font-semibold text-amber-900">
            This organisation has more active users than the current plan
            includes. Existing users keep access, but no new users can be
            activated until an administrator and support resolve the limit.
          </p>
        ) : null}
      </div>

      <div className="mt-6">
        <h3 className="text-sm font-bold text-slate-950">Modules available</h3>
        {commercial.modules.length === 0 ? (
          <p role="status" className="mt-3 text-sm text-slate-600">
            Module information is not available yet. Contact support before
            relying on this plan.
          </p>
        ) : (
          <ul
            className="mt-3 grid gap-3 sm:grid-cols-2"
            aria-label="Commercial module access"
          >
            {commercial.modules.map((module) => (
              <li
                key={module.code}
                className="min-w-0 rounded-xl border border-slate-200 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-slate-950">
                    {module.displayName}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
                    {module.accessLevel === "write"
                      ? "Included"
                      : module.accessLevel === "read"
                        ? "View only"
                        : "Not included"}
                  </span>
                </div>
                {module.commerciallyIncluded &&
                module.accessLevel !== "none" &&
                module.operationalStatus !== "available" ? (
                  <p className="mt-2 text-xs leading-5 text-slate-600">
                    {module.operationalStatus === "mock_only"
                      ? "Included commercially; only the clearly labelled test provider is available here."
                      : "Included commercially; the operational provider is not available yet."}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="mt-5 text-xs leading-5 text-slate-500">
        Plan access is managed by authorised support until billing is
        implemented. This page does not show payment, invoice or Credit
        balances.
      </p>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 break-words text-lg font-semibold capitalize text-slate-950">
        {value}
      </p>
    </div>
  );
}
