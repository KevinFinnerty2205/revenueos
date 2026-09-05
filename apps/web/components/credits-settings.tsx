"use client";

import type {
  CreditLedgerEventType,
  CreditsProjection,
} from "@revenueos/shared";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

const activityLabels: Record<CreditLedgerEventType, string> = {
  purchase: "Purchase",
  promotional_grant: "Promotional grant",
  reservation: "Reserved",
  consumption: "Used",
  release: "Released",
  refund: "Refund",
  correction: "Correction",
  expiry: "Expired",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatMoney(amountMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
  }).format(amountMinorUnits / 100);
}

function activityAmount(
  availableChange: number,
  reservedChange: number,
): string {
  const amount =
    availableChange !== 0 ? availableChange : -Math.abs(reservedChange);
  return `${amount > 0 ? "+" : ""}${amount.toLocaleString("en-AU")}`;
}

export function CreditsSettings() {
  const [credits, setCredits] = useState<CreditsProjection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const load = useCallback(async (signal: AbortSignal) => {
    setError(null);
    setCredits(
      await apiRequest<CreditsProjection>("/api/v1/credits", { signal }),
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
              : "Credit information could not be loaded.",
          );
        }
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load, retryKey]);

  if (error && !credits) {
    return (
      <section className="form-card" aria-labelledby="credits-title">
        <h2 id="credits-title" className="form-legend">
          Oryntela Credits
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

  if (!credits) {
    return (
      <section className="form-card" aria-labelledby="credits-title">
        <h2 id="credits-title" className="form-legend">
          Oryntela Credits
        </h2>
        <p role="status" className="mt-3 text-sm text-slate-600">
          Loading Credit information…
        </p>
      </section>
    );
  }

  return (
    <section
      className="form-card min-w-0 overflow-hidden"
      aria-labelledby="credits-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Commercial controls
          </p>
          <h2 id="credits-title" className="form-legend mt-2">
            Oryntela Credits
          </h2>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-950">
          Test pricing only
        </span>
      </div>

      <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-700">
        {credits.message}
      </p>

      <dl className="mt-5 grid min-w-0 gap-3 sm:grid-cols-3">
        <CreditMetric
          label="Available"
          value={credits.balance.available}
          prominent
        />
        <CreditMetric
          label="Purchased"
          value={credits.balance.purchasedAvailable}
        />
        <CreditMetric
          label="Promotional"
          value={credits.balance.promotionalAvailable}
        />
      </dl>
      {credits.balance.reserved > 0 ? (
        <p className="mt-3 text-sm text-slate-600">
          {credits.balance.reserved.toLocaleString("en-AU")} Credits are
          reserved for in-flight work and are excluded from Available.
        </p>
      ) : null}

      <div className="mt-7">
        <h3 className="text-sm font-bold text-slate-950">Recent activity</h3>
        {credits.recentActivity.length ? (
          <ul className="mt-3 divide-y divide-slate-200 rounded-xl border border-slate-200">
            {credits.recentActivity.map((item) => (
              <li
                key={item.id}
                className="grid min-w-0 gap-1 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4"
              >
                <div className="min-w-0">
                  <p className="font-semibold text-slate-950">
                    {activityLabels[item.eventType]}
                  </p>
                  <p className="mt-1 break-words text-xs text-slate-500">
                    {formatDate(item.createdAt)} · {item.creditType}
                  </p>
                </div>
                <span className="font-bold tabular-nums text-slate-950">
                  {activityAmount(item.availableChange, item.reservedChange)}{" "}
                  Credits
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-600">
            No Credit activity yet.
          </p>
        )}
      </div>

      {credits.testPacks.length ? (
        <div className="mt-7 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <h3 className="text-sm font-bold text-amber-950">
            Test catalogue — purchasing disabled
          </h3>
          <p className="mt-2 text-sm leading-6 text-amber-900">
            These deterministic packs validate payment and ledger behaviour.
            They are not public Oryntela prices and cannot be purchased here.
          </p>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {credits.testPacks.map((pack) => (
              <li
                key={pack.id}
                className="min-w-0 rounded-lg border border-amber-200 bg-white p-3"
              >
                <p className="font-semibold text-slate-950">
                  {pack.displayName}
                </p>
                <p className="mt-1 text-sm text-slate-700">
                  {pack.creditQuantity.toLocaleString("en-AU")} Credits ·{" "}
                  {formatMoney(pack.amountMinorUnits, pack.currency)}
                </p>
                <p className="mt-1 break-words text-xs font-bold uppercase tracking-wide text-amber-900">
                  {pack.pricingNote}
                </p>
                <button
                  type="button"
                  className="secondary-button mt-3 w-full sm:w-auto"
                  disabled
                  aria-describedby={`pack-${pack.id}-disabled`}
                >
                  Purchase unavailable
                </button>
                <span id={`pack-${pack.id}-disabled`} className="sr-only">
                  Live Credit sales are not activated.
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-7 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
          No production Credit packs are available. Automatic top-up is off.
        </p>
      )}
    </section>
  );
}

function CreditMetric({
  label,
  value,
  prominent = false,
}: {
  label: string;
  value: number;
  prominent?: boolean;
}) {
  return (
    <div
      className={`min-w-0 rounded-xl border p-4 ${
        prominent
          ? "border-teal-200 bg-teal-50"
          : "border-slate-200 bg-slate-50"
      }`}
    >
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-2 break-words text-2xl font-bold tabular-nums text-slate-950">
        {value.toLocaleString("en-AU")}
      </dd>
    </div>
  );
}
