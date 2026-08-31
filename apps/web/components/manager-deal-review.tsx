"use client";

import type {
  ManagerDealReview,
  SalesForecastCategory,
  SalesForecastHistory,
} from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiRequest, ApiClientError } from "@/lib/api";
import { onOpportunityChanged } from "@/lib/opportunity-events";

const categoryLabels: Record<SalesForecastCategory, string> = {
  commit: "Commit",
  likely: "Likely",
  possible: "Possible",
  not_this_period: "Not this period",
};

export function ManagerDealReviewPanel({
  opportunityId,
}: {
  opportunityId: string;
}) {
  const [data, setData] = useState<ManagerDealReview | null>(null);
  const [available, setAvailable] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [category, setCategory] = useState<SalesForecastCategory | "">("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      try {
        const value = await apiRequest<ManagerDealReview>(
          `/api/v1/manager/opportunities/${opportunityId}`,
          { signal },
        );
        setData(value);
        setCategory(value.deal.managerForecast?.category ?? "");
        setAvailable(true);
        setError(null);
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError")
          return;
        if (
          caught instanceof ApiClientError &&
          (caught.status === 403 || caught.status === 404)
        ) {
          setAvailable(false);
          return;
        }
        setError(
          caught instanceof Error
            ? caught.message
            : "Manager deal review could not be loaded.",
        );
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [opportunityId],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [load, retryKey]);

  useEffect(
    () =>
      onOpportunityChanged(opportunityId, () => {
        setRetryKey((value) => value + 1);
      }),
    [opportunityId],
  );

  async function saveManagerView() {
    if (!data?.deal.expectedCloseDate || !category) return;
    setSaving(true);
    setError(null);
    try {
      await apiRequest<SalesForecastHistory>(
        `/api/v1/forecast/opportunities/${opportunityId}/manager-judgments`,
        {
          method: "POST",
          body: JSON.stringify({
            periodType: "quarter",
            periodAnchor: data.deal.expectedCloseDate,
            category,
            expectedRevisionNumber:
              data.deal.managerForecast?.revisionNumber ?? 0,
          }),
        },
      );
      setRetryKey((value) => value + 1);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The manager view could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!available) return null;
  if (loading && data === null)
    return (
      <section
        className="form-card"
        aria-label="Manager deal review"
        aria-busy="true"
      >
        Loading manager deal review…
      </section>
    );
  if (error && data === null)
    return (
      <section
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-950"
      >
        {error}
        <button
          className="ml-3 font-bold underline"
          type="button"
          onClick={() => setRetryKey((value) => value + 1)}
        >
          Try again
        </button>
      </section>
    );
  if (data === null) return null;

  return (
    <section
      aria-labelledby="manager-deal-review-title"
      className="rounded-[2rem] border border-amber-200 bg-amber-50 p-5 shadow-sm sm:p-7"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-amber-800">
            Organisation deal review
          </p>
          <h2
            id="manager-deal-review-title"
            className="mt-2 text-2xl font-semibold text-slate-950"
          >
            What matters for this deal
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            A deterministic review of current deal conditions. It evaluates the
            Opportunity, not the salesperson.
          </p>
        </div>
        <Link href="#opportunity-workspace" className="secondary-button">
          Open Sales Brain
        </Link>
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-900"
        >
          {error}
        </p>
      ) : null}

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <ForecastCard
          label="Seller view"
          value={data.deal.sellerForecast?.category}
          detail={
            data.deal.sellerForecast?.staleReasons.length
              ? "Review recommended after a deal change."
              : "Seller-owned forecast judgment."
          }
        />
        <ForecastCard
          label="Manager view"
          value={data.deal.managerForecast?.category}
          detail={
            data.deal.managerForecast?.staleReasons.length
              ? "Review recommended after a deal change."
              : "Independent organisation review."
          }
        />
        <article className="rounded-2xl border border-sky-200 bg-white p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-sky-800">
            RevenueOS historical baseline
          </p>
          <p className="mt-2 text-xl font-semibold text-slate-950">
            {formatMoney(
              data.historicalBaseline.expectedContribution,
              data.deal.currency,
            )}
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-600">
            {data.historicalBaseline.explanation}
          </p>
        </article>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
        <label className="block text-sm font-semibold text-slate-700">
          Independent manager forecast
          <select
            className="form-control mt-2 w-full sm:max-w-sm"
            value={category}
            onChange={(event) =>
              setCategory(event.target.value as SalesForecastCategory)
            }
            disabled={!data.deal.expectedCloseDate}
          >
            <option value="">Choose a category</option>
            {Object.entries(categoryLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary-button mt-3"
          type="button"
          disabled={saving || !category || !data.deal.expectedCloseDate}
          onClick={() => void saveManagerView()}
        >
          {saving
            ? "Saving…"
            : data.deal.managerForecast
              ? "Save new manager revision"
              : "Save manager view"}
        </button>
        <p className="mt-2 text-xs text-slate-500">
          Uses the same explicit categories. It never overwrites or blends with
          the seller view.
        </p>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-2">
        <ReviewSection
          title="Why this needs attention"
          empty="No current deal-attention conditions are identified."
        >
          {data.deal.reasons.map((reason) => (
            <article
              key={reason.id}
              className="rounded-xl border border-amber-200 bg-white p-4"
            >
              <h4 className="font-semibold text-slate-950">{reason.label}</h4>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {reason.explanation}
              </p>
              <Sources sources={reason.sources} />
            </article>
          ))}
        </ReviewSection>
        <ReviewSection
          title="Questions to discuss"
          empty="No priority discussion questions are currently identified from RevenueOS evidence and deal state."
        >
          {data.questions.map((question) => (
            <article
              key={question.id}
              className="rounded-xl border border-teal-200 bg-white p-4"
            >
              <h4 className="font-semibold leading-6 text-teal-950">
                {question.question}
              </h4>
              <details className="mt-2 text-sm text-slate-600">
                <summary className="cursor-pointer font-semibold text-teal-800">
                  Why this question?
                </summary>
                <p className="mt-2 leading-6">{question.whyShown}</p>
                <Sources sources={question.sources} />
              </details>
            </article>
          ))}
        </ReviewSection>
        <ReviewSection
          title="Current Actions"
          empty="No current Actions are linked to this Opportunity."
        >
          {data.currentActions.map((action) => (
            <article
              key={action.id}
              className="rounded-xl border border-slate-200 bg-white p-4"
            >
              <p className="font-semibold text-slate-950">{action.title}</p>
              <p className="mt-1 text-xs text-slate-500">
                {action.priority} priority ·{" "}
                {action.status.replaceAll("_", " ")}
                {action.dueAt ? ` · due ${formatDateTime(action.dueAt)}` : ""}
              </p>
            </article>
          ))}
        </ReviewSection>
        <ReviewSection
          title="What changed"
          empty="No bounded deal changes are available in the recent window."
        >
          {data.recentChanges.map((change) => (
            <article
              key={change.id}
              className="rounded-xl border border-slate-200 bg-white p-4"
            >
              <p className="font-semibold text-slate-950">{change.label}</p>
              <p className="mt-1 text-xs text-slate-500">
                {formatDateTime(change.changedAt)} · {change.source.label}
              </p>
            </article>
          ))}
        </ReviewSection>
      </div>
      {data.latestInteraction ? (
        <p className="mt-5 text-sm text-slate-600">
          <strong>Latest customer interaction:</strong>{" "}
          {data.latestInteraction.title} ·{" "}
          {formatDateTime(data.latestInteraction.occurredAt)}
        </p>
      ) : null}
    </section>
  );
}

function ForecastCard({
  label,
  value,
  detail,
}: {
  label: string;
  value?: SalesForecastCategory;
  detail: string;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-xl font-semibold text-slate-950">
        {value ? categoryLabels[value] : "Not reviewed"}
      </p>
      <p className="mt-2 text-xs leading-5 text-slate-600">{detail}</p>
    </article>
  );
}

function ReviewSection({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: React.ReactNode;
}) {
  const hasChildren = Array.isArray(children)
    ? children.length > 0
    : children !== null;
  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-100/40 p-4">
      <h3 className="text-lg font-semibold text-slate-950">{title}</h3>
      <div className="mt-3 space-y-3">
        {hasChildren ? (
          children
        ) : (
          <p className="text-sm leading-6 text-slate-600">{empty}</p>
        )}
      </div>
    </section>
  );
}

function Sources({
  sources,
}: {
  sources: ManagerDealReview["deal"]["reasons"][number]["sources"];
}) {
  return (
    <details className="mt-3 text-xs text-slate-500">
      <summary className="cursor-pointer font-semibold text-teal-800">
        Sources
      </summary>
      <ul className="mt-2 space-y-1">
        {sources.map((source) => (
          <li key={`${source.sourceType}-${source.sourceId}`}>
            {source.href ? (
              <Link className="hover:underline" href={source.href}>
                {source.label}
              </Link>
            ) : (
              source.label
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}

function formatMoney(value: string | null, currency: string | null) {
  if (value === null || currency === null) return "Unavailable";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}
