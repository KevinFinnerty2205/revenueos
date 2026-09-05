"use client";

import type { BillingSuccessStatus } from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function BillingSuccess() {
  const [status, setStatus] = useState<BillingSuccessStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const load = useCallback(async (signal: AbortSignal) => {
    setError(null);
    setStatus(
      await apiRequest<BillingSuccessStatus>("/api/v1/billing/success-status", {
        signal,
      }),
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
              : "Payment status could not be checked.",
          );
        }
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load, retryKey]);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
          Test billing
        </p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950">
          {status?.confirmed
            ? "Payment confirmed"
            : "Payment confirmation pending"}
        </h1>
      </div>
      <section className="form-card" aria-labelledby="payment-status-title">
        <h2 id="payment-status-title" className="form-legend">
          Server-verified status
        </h2>
        {!status && !error ? (
          <p role="status" className="mt-3 text-sm text-slate-600">
            Checking verified provider status…
          </p>
        ) : null}
        {status ? (
          <p
            role="status"
            className={`mt-3 text-sm leading-6 ${status.confirmed ? "text-teal-900" : "text-amber-900"}`}
          >
            {status.message}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="mt-3 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Visiting this page never grants plan access. Only a verified provider
          event and server reconciliation can activate a subscription.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          {!status?.confirmed ? (
            <button
              type="button"
              className="secondary-button"
              onClick={() => setRetryKey((value) => value + 1)}
            >
              Check status again
            </button>
          ) : null}
          <Link href="/settings" className="primary-button">
            Return to billing settings
          </Link>
        </div>
      </section>
    </div>
  );
}
