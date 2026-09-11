"use client";

import type { TermsAcceptanceStatus } from "@revenueos/shared";
import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";

type AcceptanceSource =
  "trial_onboarding" | "subscription_checkout" | "administrative_onboarding";

interface TermsAcceptanceProps {
  source: AcceptanceSource;
  children?: ReactNode;
  onAcceptanceChange?: (accepted: boolean) => void;
}

export function TermsAcceptance({
  source,
  children,
  onAcceptanceChange,
}: TermsAcceptanceProps) {
  const [status, setStatus] = useState<TermsAcceptanceStatus | null>(null);
  const [checked, setChecked] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justAccepted, setJustAccepted] = useState(false);
  const confirmationRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<TermsAcceptanceStatus>("/api/v1/legal/terms-acceptance", {
      signal: controller.signal,
    })
      .then(setStatus)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Terms acceptance could not be loaded.",
          );
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    onAcceptanceChange?.(status?.accepted === true);
  }, [onAcceptanceChange, status?.accepted]);

  useEffect(() => {
    if (justAccepted) confirmationRef.current?.focus();
  }, [justAccepted]);

  async function accept(): Promise<void> {
    if (!checked) return;
    setSaving(true);
    setError(null);
    try {
      const accepted = await apiRequest<TermsAcceptanceStatus>(
        "/api/v1/legal/terms-acceptance",
        {
          method: "POST",
          body: JSON.stringify({
            authorityAndTermsAccepted: true,
            source,
          }),
        },
      );
      setStatus(accepted);
      setChecked(false);
      setJustAccepted(true);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Terms acceptance could not be recorded.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (error && !status) {
    return (
      <p
        role="alert"
        className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-900"
      >
        {error}
      </p>
    );
  }

  if (!status) {
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading Terms status…
      </p>
    );
  }

  if (status.accepted) {
    return (
      <>
        <p
          ref={confirmationRef}
          role="status"
          tabIndex={justAccepted ? -1 : undefined}
          className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950 outline-none focus-visible:ring-2 focus-visible:ring-brand-secondary"
        >
          Current Terms accepted for this organisation
          {status.evidence
            ? ` on ${new Intl.DateTimeFormat("en-AU", {
                dateStyle: "long",
                timeZone: "UTC",
              }).format(new Date(status.evidence.acceptedAt))}.`
            : "."}
        </p>
        {children}
      </>
    );
  }

  return (
    <section
      className="form-card min-w-0 overflow-hidden"
      aria-labelledby={`terms-acceptance-title-${source}`}
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
        {status.terms.status === "draft"
          ? "Owner-review draft · test only"
          : "Organisation agreement"}
      </p>
      <h2
        id={`terms-acceptance-title-${source}`}
        className="mt-2 text-2xl font-semibold text-slate-950"
      >
        Accept the current Terms to continue
      </h2>
      <p className="mt-3 text-sm leading-6 text-slate-700">{status.message}</p>
      <p className="mt-3 text-sm leading-6 text-slate-700">
        Read the{" "}
        <Link
          className="font-semibold text-brand-secondary underline"
          href={status.terms.href}
        >
          Oryntela Terms &amp; Conditions
        </Link>{" "}
        and review the{" "}
        <Link
          className="font-semibold text-brand-secondary underline"
          href={status.privacyNotice.href}
        >
          Privacy Policy
        </Link>{" "}
        as notice. The Privacy Policy is not a separate contract acceptance.
      </p>

      {status.canAccept ? (
        <>
          <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-slate-300 p-4 text-sm leading-6 text-slate-800 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-secondary">
            <input
              type="checkbox"
              checked={checked}
              onChange={(event) => setChecked(event.target.checked)}
              className="mt-1 h-4 w-4 shrink-0"
            />
            <span>
              I confirm that I am authorised to act for this organisation and
              agree to the Oryntela Terms &amp; Conditions on its behalf.
            </span>
          </label>
          <button
            type="button"
            className="primary-button mt-4"
            disabled={!checked || saving}
            onClick={() => void accept()}
          >
            {saving ? "Recording acceptance…" : "Accept Terms for organisation"}
          </button>
        </>
      ) : null}

      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
    </section>
  );
}
