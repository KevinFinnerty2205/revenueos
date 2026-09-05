"use client";

import type { CreditQuote, ProspectAvailability } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";

type ProspectActionCode =
  "PROSPECT_COMPANY_RESEARCH" | "PROSPECT_PERSON_RESEARCH";

interface ProspectCreditActionProps {
  actionCode: ProspectActionCode;
  label: string;
  busyLabel: string;
  className: string;
  disabled?: boolean;
  executionMode?: ProspectAvailability["executionMode"];
  onAuthorised: (
    creditQuoteId: string | null,
    idempotencyKey: string,
  ) => Promise<boolean>;
}

export function ProspectCreditAction({
  actionCode,
  label,
  busyLabel,
  className,
  disabled = false,
  executionMode,
  onAuthorised,
}: ProspectCreditActionProps) {
  const [open, setOpen] = useState(false);
  const [quote, setQuote] = useState<CreditQuote | null>(null);
  const [requestKey, setRequestKey] = useState<string | null>(null);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!open) return;
    const returnFocus = trigger.current;
    heading.current?.focus();
    function manageKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape" && !running) {
        setOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const controls = dialog.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!controls || controls.length === 0) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === heading.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", manageKeyboard);
    return () => {
      window.removeEventListener("keydown", manageKeyboard);
      returnFocus?.focus();
    };
  }, [open, running]);

  async function begin() {
    setError(null);
    setRunning(true);
    const key = `prospect:${actionCode.toLowerCase()}:${crypto.randomUUID()}`;
    setRequestKey(key);
    try {
      const mode =
        executionMode ??
        (
          await apiRequest<ProspectAvailability>(
            "/api/v1/prospect/availability",
          )
        ).executionMode;
      if (mode === "unavailable") {
        setError("Provider-backed research is temporarily unavailable.");
        return;
      }
      if (mode === "demo") {
        if (!(await onAuthorised(null, key))) {
          setError("Research could not be started. Try again.");
        }
        return;
      }
      setOpen(true);
      setLoadingQuote(true);
      setQuote(
        await apiRequest<CreditQuote>("/api/v1/credits/quotes", {
          method: "POST",
          body: JSON.stringify({ actionCode, quantity: 1 }),
        }),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Credit quote could not be loaded.",
      );
    } finally {
      setLoadingQuote(false);
      setRunning(false);
    }
  }

  async function confirm() {
    if (!quote || !requestKey || !quote.sufficientBalance) return;
    setRunning(true);
    setError(null);
    try {
      if (await onAuthorised(quote.quoteId, requestKey)) {
        setOpen(false);
        setQuote(null);
        setRequestKey(null);
      } else {
        setError(
          "Research did not start. Retry this confirmation to reuse the same quote safely.",
        );
      }
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <span className="inline-flex flex-col items-start gap-2">
        <button
          ref={trigger}
          type="button"
          className={className}
          disabled={disabled || running}
          onClick={() => void begin()}
        >
          {running && !open ? busyLabel : label}
        </button>
        {error && !open ? (
          <span
            role="alert"
            className="max-w-sm text-sm font-medium text-rose-700"
          >
            {error}
          </span>
        ) : null}
      </span>

      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="prospect-credit-title"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
        >
          <div
            ref={dialog}
            className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl sm:p-8"
          >
            <h2
              id="prospect-credit-title"
              ref={heading}
              tabIndex={-1}
              className="text-2xl font-semibold tracking-tight text-slate-950 outline-none"
            >
              Confirm Credit spend
            </h2>
            {loadingQuote ? (
              <p role="status" className="mt-4 text-sm text-slate-600">
                Loading the server-owned Credit quote…
              </p>
            ) : quote ? (
              <>
                <dl className="mt-5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-3 rounded-2xl bg-slate-50 p-4 text-sm">
                  <dt className="text-slate-600">Action</dt>
                  <dd className="text-right font-semibold text-slate-950">
                    {quote.actionName}
                  </dd>
                  <dt className="text-slate-600">Quantity</dt>
                  <dd className="text-right font-semibold text-slate-950">
                    {quote.quantity}
                  </dd>
                  <dt className="text-slate-600">Maximum cost</dt>
                  <dd className="text-right font-semibold text-slate-950">
                    {quote.maximumCreditCost.toLocaleString("en-AU")} Credits
                  </dd>
                  <dt className="text-slate-600">Available balance</dt>
                  <dd className="text-right font-semibold text-slate-950">
                    {quote.currentBalance.toLocaleString("en-AU")} Credits
                  </dd>
                </dl>
                <p className="mt-4 text-xs leading-5 text-slate-500">
                  {quote.pricingNotice}
                </p>
                {!quote.sufficientBalance ? (
                  <div
                    role="alert"
                    className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
                  >
                    <p className="font-semibold">Insufficient Credits</p>
                    <p className="mt-1 leading-6">
                      No provider request will be made. Credits are granted only
                      after verified payment; invoice issue or pending payment
                      never authorises research.
                    </p>
                    <Link href="/settings" className="secondary-button mt-3">
                      View Credits
                    </Link>
                  </div>
                ) : null}
              </>
            ) : null}
            {error ? (
              <p
                role="alert"
                className="mt-4 text-sm font-medium text-rose-700"
              >
                {error}
              </p>
            ) : null}
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                className="secondary-button"
                disabled={running}
                onClick={() => setOpen(false)}
              >
                {quote?.sufficientBalance ? "Cancel" : "Close"}
              </button>
              {quote?.sufficientBalance ? (
                <button
                  type="button"
                  className="primary-button"
                  disabled={running}
                  onClick={() => void confirm()}
                >
                  {running
                    ? "Reserving Credits…"
                    : `Confirm ${quote.maximumCreditCost.toLocaleString("en-AU")} Credits`}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
