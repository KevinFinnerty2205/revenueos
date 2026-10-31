"use client";

import type { MeResponse } from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { BetaAdmin } from "@/components/beta-admin";
import { ConversationDeliveryPreferences } from "@/components/conversation-delivery-preferences";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";

export function SettingsExperience() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const load = useCallback(async (signal: AbortSignal) => {
    setError(null);
    const next = await apiRequest<MeResponse>("/api/v1/me", { signal });
    setMe(next);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void load(controller.signal).catch((reason: unknown) =>
        !controller.signal.aborted
          ? setError(
              reason instanceof Error
                ? reason.message
                : "Workspace settings could not be loaded.",
            )
          : undefined,
      );
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load, retryKey]);

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Workspace"
          title="Settings"
          description="Manage your Oryntela workspace experience."
        />
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5">
          <h2 className="font-semibold text-rose-950">
            Settings are unavailable
          </h2>
          <p role="alert" className="mt-2 text-sm text-rose-900">
            {error}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              className="secondary-button"
              onClick={() => setRetryKey((value) => value + 1)}
            >
              Try again
            </button>
            <Link href="/dashboard" className="secondary-button">
              Return Home
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!me) {
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading settings…
      </p>
    );
  }

  const isAdmin = me.role === "admin";

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={isAdmin ? "Workspace administration" : "Workspace"}
        title="Settings"
        description={
          isAdmin
            ? "Manage conversation briefings, members, data and private-beta safety controls."
            : "Review your workspace identity and return to the guidance that helps you get started."
        }
      />

      <section className="form-card" aria-labelledby="account-settings-title">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
          Your access
        </p>
        <h2 id="account-settings-title" className="form-legend mt-2">
          {me.user.displayName}
        </h2>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="font-semibold text-slate-500">Organisation</dt>
            <dd className="mt-1 text-slate-950">{me.organisation.name}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-500">Access level</dt>
            <dd className="mt-1 capitalize text-slate-950">{me.role}</dd>
          </div>
        </dl>
        <Link href="/onboarding" className="secondary-button mt-5">
          Revisit getting started
        </Link>
      </section>

      <ConversationDeliveryPreferences />

      {isAdmin ? (
        <>
          <nav
            aria-label="Settings sections"
            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
              Go to
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {[
                {
                  href: "/knowledge",
                  label: "Company knowledge",
                  detail: "Sources and approved company understanding",
                },
                {
                  href: "/frameworks",
                  label: "Frameworks",
                  detail: "Notes-only, BANT, SPICED, MEDDICC or MEDDPICC",
                },
                {
                  href: "#workspace-administration",
                  label: "Team & safety",
                  detail: "Members, data, integrations and diagnostics",
                },
              ].map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className="rounded-xl border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-focus"
                >
                  <span className="block font-semibold text-slate-950">
                    {item.label}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">
                    {item.detail}
                  </span>
                </a>
              ))}
            </div>
          </nav>
          <div id="workspace-administration" className="scroll-mt-6 space-y-8">
            <BetaAdmin currentUserId={me.user.id} />
          </div>
        </>
      ) : (
        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="font-semibold text-slate-950">
            Organisation controls
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Your organisation administrator manages methodology, members,
            consent, retention and private-beta feature controls.
          </p>
        </section>
      )}
    </div>
  );
}
