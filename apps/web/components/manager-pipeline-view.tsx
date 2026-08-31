"use client";

import type {
  ManagerDealAttentionList,
  SalesForecastCategory,
} from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

const forecastLabels: Record<SalesForecastCategory, string> = {
  commit: "Commit",
  likely: "Likely",
  possible: "Possible",
  not_this_period: "Not this period",
};

export function ManagerPipelineView({
  pipelineId,
  ownerUserId,
}: {
  pipelineId: string;
  ownerUserId: string;
}) {
  const [data, setData] = useState<ManagerDealAttentionList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ pageSize: "50" });
    if (pipelineId) query.set("pipelineId", pipelineId);
    if (ownerUserId) query.set("ownerUserId", ownerUserId);
    const timeout = window.setTimeout(() => {
      setLoading(true);
      void apiRequest<ManagerDealAttentionList>(
        `/api/v1/manager/deal-attention?${query.toString()}`,
        {
          signal: controller.signal,
        },
      )
        .then((value) => {
          setData(value);
          setError(null);
        })
        .catch((caught: unknown) => {
          if (caught instanceof DOMException && caught.name === "AbortError")
            return;
          setError(
            caught instanceof Error
              ? caught.message
              : "Manager view could not be loaded.",
          );
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [ownerUserId, pipelineId, retryKey]);

  if (loading)
    return (
      <div role="status" className="form-card">
        Loading deal attention…
      </div>
    );
  if (error)
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-red-950">
        <p role="alert">{error}</p>
        <button
          type="button"
          className="secondary-button mt-4"
          onClick={() => setRetryKey((value) => value + 1)}
        >
          Try again
        </button>
      </div>
    );
  if (data === null) return null;

  return (
    <section aria-labelledby="manager-pipeline-title" className="space-y-5">
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <h2
          id="manager-pipeline-title"
          className="text-xl font-semibold text-slate-950"
        >
          Manager view · deals needing attention
        </h2>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          Deal conditions are ordered by close date, Actions, evidence and
          forecast state. There is no health score or people ranking.
        </p>
        {data.summaries.length ? (
          <dl className="mt-4 flex flex-wrap gap-2">
            {data.summaries.map((summary) => (
              <div
                key={summary.code}
                className="rounded-full border border-amber-200 bg-white px-3 py-1.5 text-xs text-amber-950"
              >
                <dt className="inline font-semibold">{summary.label}</dt>{" "}
                <dd className="inline">{summary.dealCount}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
      {data.items.length ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {data.items.map((item) => (
            <article
              key={item.opportunityId}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <Link
                    href={item.href}
                    className="text-lg font-semibold text-teal-900 hover:underline"
                  >
                    {item.opportunityName}
                  </Link>
                  <p className="mt-1 text-sm text-slate-600">
                    {item.companyName ?? "No account"} · {item.ownerDisplayName}
                  </p>
                </div>
                <p className="text-right text-sm font-semibold text-slate-700">
                  {formatMoney(item.amount, item.currency)}
                  <br />
                  <span className="font-normal text-slate-500">
                    Close {formatDate(item.expectedCloseDate)}
                  </span>
                </p>
              </div>
              <p className="mt-3 text-sm text-slate-700">
                {item.pipelineName} · {item.stageName}
              </p>
              <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                <div className="rounded-xl bg-slate-50 p-3">
                  <dt className="font-semibold text-slate-600">Seller view</dt>
                  <dd className="mt-1 text-slate-950">
                    {forecast(item.sellerForecast?.category)}
                  </dd>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <dt className="font-semibold text-slate-600">Manager view</dt>
                  <dd className="mt-1 text-slate-950">
                    {forecast(item.managerForecast?.category)}
                  </dd>
                </div>
              </dl>
              <ul className="mt-4 space-y-2">
                {item.reasons.map((reason) => (
                  <li
                    key={reason.id}
                    className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950"
                  >
                    <strong>{reason.label}.</strong> {reason.explanation}
                  </li>
                ))}
              </ul>
              <Link
                href={item.href}
                className="mt-4 inline-block text-sm font-semibold text-teal-800 hover:underline"
              >
                Review Opportunity →
              </Link>
            </article>
          ))}
        </div>
      ) : (
        <div className="form-card text-center">
          <h2 className="text-xl font-semibold text-slate-950">
            No deals need attention
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Nothing currently matches the selected deal-attention conditions.
          </p>
        </div>
      )}
    </section>
  );
}

function forecast(category: SalesForecastCategory | undefined) {
  return category ? forecastLabels[category] : "Not reviewed";
}

function formatMoney(value: string | null, currency: string | null) {
  if (value === null || currency === null) return "Value not set";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function formatDate(value: string | null) {
  if (value === null) return "not set";
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
