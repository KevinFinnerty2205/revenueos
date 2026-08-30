"use client";

import type {
  SalesForecastCalibration,
  SalesForecastCategory,
  SalesForecastHistory,
  SalesForecastMetadata,
  SalesForecastOpportunity,
  SalesForecastPeriodType,
  SalesForecastResponse,
} from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";

const categoryLabels: Record<SalesForecastCategory, string> = {
  commit: "Commit",
  likely: "Likely",
  possible: "Possible",
  not_this_period: "Not this period",
};

function localDate(value = new Date()): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shiftAnchor(
  anchor: string,
  periodType: SalesForecastPeriodType,
  direction: number,
): string {
  const [year, month, day] = anchor.split("-").map(Number);
  const next = new Date(year ?? 0, (month ?? 1) - 1, day ?? 1);
  next.setDate(1);
  next.setMonth(next.getMonth() + direction * (periodType === "month" ? 1 : 3));
  return localDate(next);
}

function formatMoney(amount: string | null, currency: string): string {
  if (amount === null) return "Unavailable";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function staleLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function SummaryCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold text-slate-600">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
        {value}
      </p>
      <p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p>
    </article>
  );
}

function ForecastHistory({ history }: { history: SalesForecastHistory }) {
  if (!history.revisions.length) {
    return (
      <p className="mt-3 text-sm text-slate-500">
        No seller judgment has been recorded for this period.
      </p>
    );
  }
  return (
    <ol className="mt-4 space-y-3 border-l-2 border-slate-200 pl-4">
      {history.revisions.map((revision) => (
        <li key={revision.id} className="text-sm text-slate-700">
          <p className="font-semibold text-slate-900">
            Revision {revision.revisionNumber}:{" "}
            {categoryLabels[revision.category]}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {revision.createdByDisplayName} ·{" "}
            {formatDate(revision.createdAt.slice(0, 10))} · snapshot{" "}
            {formatMoney(
              revision.amountSnapshot,
              revision.currencySnapshot ?? "AUD",
            )}{" "}
            · {revision.stageNameSnapshot}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Historical model at review: {revision.historicalBaseline.sampleSize}{" "}
            outcomes;{" "}
            {revision.historicalBaseline.observedWinRate === null
              ? "no rate shown"
              : `${revision.historicalBaseline.observedWinRate}% won`}
            .
          </p>
        </li>
      ))}
    </ol>
  );
}

function OpportunityForecastCard({
  opportunity,
  currency,
  periodType,
  periodAnchor,
  periodLocked,
  canReview,
  onSaved,
}: {
  opportunity: SalesForecastOpportunity;
  currency: string;
  periodType: SalesForecastPeriodType;
  periodAnchor: string;
  periodLocked: boolean;
  canReview: boolean;
  onSaved: () => void;
}) {
  const [category, setCategory] = useState<SalesForecastCategory | "">(
    opportunity.judgment?.category ?? "",
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [history, setHistory] = useState<SalesForecastHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  async function saveJudgment() {
    if (!category) return;
    setSaving(true);
    setMessage(null);
    try {
      const saved = await apiRequest<SalesForecastHistory>(
        `/api/v1/forecast/opportunities/${opportunity.opportunityId}/judgments`,
        {
          method: "POST",
          body: JSON.stringify({
            periodType,
            periodAnchor,
            category,
            expectedRevisionNumber: opportunity.judgment?.revisionNumber ?? 0,
          }),
        },
      );
      setHistory(saved);
      setMessage("Seller judgment saved as a new revision.");
      onSaved();
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "The seller judgment could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function loadHistory() {
    if (history) {
      setHistory(null);
      return;
    }
    setHistoryLoading(true);
    setMessage(null);
    try {
      const query = new URLSearchParams({ periodType, periodAnchor });
      setHistory(
        await apiRequest<SalesForecastHistory>(
          `/api/v1/forecast/opportunities/${opportunity.opportunityId}/history?${query.toString()}`,
        ),
      );
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Forecast history could not be loaded.",
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  const baseline = opportunity.historicalBaseline;
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/opportunities/${opportunity.opportunityId}`}
              className="text-lg font-semibold text-teal-900 hover:underline"
            >
              {opportunity.opportunityName}
            </Link>
            {opportunity.judgment?.staleReasons.length ? (
              <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-900">
                Needs review
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {opportunity.companyName ?? "No company"} ·{" "}
            {opportunity.ownerDisplayName}
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-800">
            {formatMoney(opportunity.amount, currency)} ·{" "}
            {opportunity.stageName} · closes{" "}
            {formatDate(opportunity.expectedCloseDate)}
          </p>
          {opportunity.judgment?.staleReasons.length ? (
            <p className="mt-2 text-xs text-amber-800">
              Changed since review:{" "}
              {opportunity.judgment.staleReasons.map(staleLabel).join(", ")}.
            </p>
          ) : null}
        </div>
        <div className="w-full lg:max-w-sm">
          <label className="text-sm font-semibold text-slate-700">
            Seller category
            <select
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as SalesForecastCategory)
              }
              disabled={!canReview || periodLocked}
              className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm disabled:bg-slate-100"
            >
              {!category ? <option value="">Choose a category</option> : null}
              {Object.entries(categoryLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {canReview ? (
            <button
              type="button"
              onClick={() => void saveJudgment()}
              disabled={saving || periodLocked || !category}
              className="mt-2 min-h-11 w-full rounded-xl bg-teal-800 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {saving
                ? "Saving…"
                : opportunity.judgment
                  ? "Save new revision"
                  : "Save judgment"}
            </button>
          ) : (
            <p className="mt-2 text-xs text-slate-500">
              Only the current owner can review this deal.
            </p>
          )}
        </div>
      </div>
      <details className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-800">
          Historical baseline details
        </summary>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          {baseline.explanation}
        </p>
        <dl className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
          <div>
            <dt className="font-semibold">Comparable outcomes</dt>
            <dd>{baseline.sampleSize}</dd>
          </div>
          <div>
            <dt className="font-semibold">Observed win rate</dt>
            <dd>
              {baseline.observedWinRate === null
                ? "Not shown"
                : `${baseline.observedWinRate}%`}
            </dd>
          </div>
          <div>
            <dt className="font-semibold">Expected contribution</dt>
            <dd>{formatMoney(baseline.expectedContribution, currency)}</dd>
          </div>
        </dl>
      </details>
      <button
        type="button"
        onClick={() => void loadHistory()}
        className="mt-4 text-sm font-semibold text-teal-800 underline-offset-4 hover:underline"
      >
        {historyLoading
          ? "Loading history…"
          : history
            ? "Hide review history"
            : "View review history"}
      </button>
      {history ? <ForecastHistory history={history} /> : null}
      {message ? (
        <p role="status" className="mt-3 text-sm text-slate-700">
          {message}
        </p>
      ) : null}
    </article>
  );
}

export function SalesForecast() {
  const [metadata, setMetadata] = useState<SalesForecastMetadata | null>(null);
  const [forecast, setForecast] = useState<SalesForecastResponse | null>(null);
  const [calibration, setCalibration] =
    useState<SalesForecastCalibration | null>(null);
  const [periodType, setPeriodType] =
    useState<SalesForecastPeriodType>("quarter");
  const [periodAnchor, setPeriodAnchor] = useState(localDate);
  const [currency, setCurrency] = useState("AUD");
  const [pipelineId, setPipelineId] = useState("");
  const [ownerUserId, setOwnerUserId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<SalesForecastMetadata>("/api/v1/forecast/metadata", {
      signal: controller.signal,
    })
      .then((value) => {
        setMetadata(value);
        if (!value.canViewOrganisationForecast)
          setOwnerUserId(value.currentUserId);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted)
          setError(
            caught instanceof Error
              ? caught.message
              : "Forecast metadata could not be loaded.",
          );
      });
    return () => controller.abort();
  }, [retryKey]);

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError(null);
      const query = new URLSearchParams({
        periodType,
        periodAnchor,
        currency: currency.trim().toUpperCase(),
        pageSize: "100",
      });
      if (pipelineId) query.set("pipelineId", pipelineId);
      if (ownerUserId) query.set("ownerUserId", ownerUserId);
      try {
        const [loadedForecast, loadedCalibration] = await Promise.all([
          apiRequest<SalesForecastResponse>(
            `/api/v1/forecast?${query.toString()}`,
            { signal },
          ),
          apiRequest<SalesForecastCalibration>(
            `/api/v1/forecast/calibration?periodType=${periodType}`,
            { signal },
          ),
        ]);
        setForecast(loadedForecast);
        setCalibration(loadedCalibration);
      } catch (caught) {
        if (!signal.aborted)
          setError(
            caught instanceof Error
              ? caught.message
              : "Sales forecasting could not be loaded.",
          );
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [currency, ownerUserId, periodAnchor, periodType, pipelineId],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [load, retryKey]);

  const targetSummary = useMemo(
    () =>
      forecast?.targets.length
        ? forecast.targets
            .map(
              (target) =>
                `${target.label}: ${formatMoney(target.targetValue, forecast.currency)}`,
            )
            .join(" · ")
        : "No matching won-value target",
    [forecast],
  );

  return (
    <div className="space-y-6">
      <section
        aria-label="Forecast filters"
        className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <label className="text-sm font-semibold text-slate-700">
            Period
            <select
              value={periodType}
              onChange={(event) =>
                setPeriodType(event.target.value as SalesForecastPeriodType)
              }
              className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2"
            >
              <option value="month">Month</option>
              <option value="quarter">Quarter</option>
            </select>
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Currency
            <input
              value={currency}
              maxLength={3}
              pattern="[A-Za-z]{3}"
              onChange={(event) =>
                setCurrency(event.target.value.toUpperCase())
              }
              className="mt-2 block w-full rounded-xl border border-slate-300 px-3 py-2 uppercase"
            />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Pipeline
            <select
              value={pipelineId}
              onChange={(event) => setPipelineId(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2"
            >
              <option value="">All pipelines</option>
              {metadata?.pipelines.map((pipeline) => (
                <option key={pipeline.id} value={pipeline.id}>
                  {pipeline.name}
                  {pipeline.active ? "" : " (inactive)"}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Owner
            <select
              value={ownerUserId}
              disabled={!metadata?.canViewOrganisationForecast}
              onChange={(event) => setOwnerUserId(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 disabled:bg-slate-100"
            >
              {metadata?.canViewOrganisationForecast ? (
                <option value="">Organisation</option>
              ) : null}
              {metadata?.owners.map((owner) => (
                <option key={owner.userId} value={owner.userId}>
                  {owner.displayName}
                  {owner.active ? "" : " (inactive)"}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={() =>
              setPeriodAnchor((value) => shiftAnchor(value, periodType, -1))
            }
            className="secondary-button"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={() => setPeriodAnchor(localDate())}
            className="secondary-button"
          >
            Current
          </button>
          <button
            type="button"
            onClick={() =>
              setPeriodAnchor((value) => shiftAnchor(value, periodType, 1))
            }
            className="secondary-button"
          >
            Next
          </button>
          <p className="ml-auto text-sm font-semibold text-slate-700">
            {forecast?.period.periodLabel ?? "Selected period"} ·{" "}
            {forecast?.period.timezone ?? metadata?.organisationTimezone}
          </p>
        </div>
      </section>

      {loading ? (
        <div
          role="status"
          className="rounded-2xl border border-slate-200 bg-white px-6 py-14 text-center text-sm font-semibold text-slate-600"
        >
          Loading transparent forecast…
        </div>
      ) : null}
      {error ? (
        <div
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-950"
        >
          <p className="font-semibold">Sales forecast is unavailable</p>
          <p className="mt-1 text-sm">{error}</p>
          <button
            type="button"
            onClick={() => setRetryKey((value) => value + 1)}
            className="mt-4 rounded-lg bg-red-900 px-4 py-2 text-sm font-semibold text-white"
          >
            Try again
          </button>
        </div>
      ) : null}

      {!loading && !error && forecast ? (
        <>
          <section aria-labelledby="forecast-summary-title">
            <h2
              id="forecast-summary-title"
              className="text-xl font-semibold text-slate-950"
            >
              Period position
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Actual, target and forecast are separate. Currency is never
              converted.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <SummaryCard
                label="Actual won"
                value={formatMoney(forecast.actual.amount, forecast.currency)}
                detail={
                  forecast.actual.calculatedThrough
                    ? `Canonical won value through ${formatDate(forecast.actual.calculatedThrough)}.`
                    : forecast.actual.state === "upcoming"
                      ? "Upcoming period; no actual yet."
                      : "Actual is unavailable."
                }
              />
              <SummaryCard
                label="Target"
                value={
                  forecast.targets.length === 1
                    ? formatMoney(
                        forecast.targets[0]?.targetValue ?? null,
                        forecast.currency,
                      )
                    : `${forecast.targets.length} matching targets`
                }
                detail={targetSummary}
              />
              <SummaryCard
                label="Seller Commit"
                value={formatMoney(
                  forecast.sellerForecast.commit.amount,
                  forecast.currency,
                )}
                detail={`${forecast.sellerForecast.commit.opportunityCount} seller-reviewed opportunities.`}
              />
              <SummaryCard
                label="RevenueOS baseline"
                value={formatMoney(
                  forecast.revenueosBaseline.expectedContribution,
                  forecast.currency,
                )}
                detail={`${forecast.revenueosBaseline.coveredOpportunityCount} covered · ${forecast.revenueosBaseline.uncoveredOpportunityCount} uncovered. Not a seller forecast.`}
              />
            </div>
          </section>

          <section
            aria-labelledby="seller-range-title"
            className="rounded-2xl border border-teal-200 bg-teal-50 p-5"
          >
            <h2
              id="seller-range-title"
              className="text-lg font-semibold text-teal-950"
            >
              Seller forecast range
            </h2>
            <p className="mt-1 text-sm leading-6 text-teal-900">
              {forecast.sellerForecast.disclosure}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <SummaryCard
                label="Commit"
                value={formatMoney(
                  forecast.sellerForecast.commit.amount,
                  forecast.currency,
                )}
                detail={`${forecast.sellerForecast.commit.opportunityCount} opportunities`}
              />
              <SummaryCard
                label="Likely case"
                value={formatMoney(
                  forecast.sellerForecast.likely.amount,
                  forecast.currency,
                )}
                detail={`Commit + Likely · ${forecast.sellerForecast.likely.opportunityCount} opportunities`}
              />
              <SummaryCard
                label="Possible case"
                value={formatMoney(
                  forecast.sellerForecast.possible.amount,
                  forecast.currency,
                )}
                detail={`Commit + Likely + Possible · ${forecast.sellerForecast.possible.opportunityCount} opportunities`}
              />
            </div>
            <p className="mt-4 text-sm text-teal-900">
              {forecast.sellerForecast.unreviewedCount} unreviewed ·{" "}
              {forecast.sellerForecast.notThisPeriodCount} marked Not this
              period · {forecast.sellerForecast.needsReviewCount} stale.
            </p>
          </section>

          <section
            aria-labelledby="baseline-title"
            className="rounded-2xl border border-sky-200 bg-sky-50 p-5"
          >
            <h2
              id="baseline-title"
              className="text-lg font-semibold text-sky-950"
            >
              Separate historical baseline
            </h2>
            <p className="mt-1 text-sm leading-6 text-sky-900">
              {forecast.revenueosBaseline.disclosure}
            </p>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="font-semibold text-sky-950">
                  Expected contribution
                </dt>
                <dd>
                  {formatMoney(
                    forecast.revenueosBaseline.expectedContribution,
                    forecast.currency,
                  )}
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-sky-950">
                  Covered live value
                </dt>
                <dd>
                  {formatMoney(
                    forecast.revenueosBaseline.coveredAmount,
                    forecast.currency,
                  )}
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-sky-950">Method</dt>
                <dd>
                  {forecast.revenueosBaseline.lookbackDays}-day history ·
                  minimum {forecast.revenueosBaseline.minimumSample} final
                  outcomes per exact stage
                </dd>
              </div>
            </dl>
          </section>

          <aside className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
            <strong>Input quality:</strong>{" "}
            {forecast.inputQuality.eligibleOpportunityCount} eligible ·{" "}
            {forecast.inputQuality.unvaluedOpportunityCount} unvalued ·{" "}
            {forecast.inputQuality.missingExpectedCloseCount} missing expected
            close date · {forecast.inputQuality.insufficientHistoryCount}{" "}
            without sufficient comparable history.
          </aside>

          <section aria-labelledby="deal-review-title">
            <h2
              id="deal-review-title"
              className="text-xl font-semibold text-slate-950"
            >
              Deal review
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Each category is an explicit seller judgment. RevenueOS does not
              infer or attach a probability.
            </p>
            <div className="mt-4 space-y-4">
              {forecast.opportunities.map((opportunity) => (
                <OpportunityForecastCard
                  key={`${opportunity.opportunityId}-${opportunity.judgment?.revisionId ?? "unreviewed"}-${periodType}-${periodAnchor}`}
                  opportunity={opportunity}
                  currency={forecast.currency}
                  periodType={periodType}
                  periodAnchor={periodAnchor}
                  periodLocked={forecast.period.status === "past"}
                  canReview={
                    opportunity.ownerUserId === metadata?.currentUserId
                  }
                  onSaved={() => setRetryKey((value) => value + 1)}
                />
              ))}
              {!forecast.opportunities.length ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
                  <p className="font-semibold text-slate-900">
                    No open opportunities close in this period
                  </p>
                  <p className="mt-2 text-sm text-slate-600">
                    Try another currency, pipeline, owner or period.
                  </p>
                </div>
              ) : null}
            </div>
          </section>

          {calibration ? (
            <section
              aria-labelledby="calibration-title"
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <h2
                id="calibration-title"
                className="text-lg font-semibold text-slate-950"
              >
                Forecast calibration
              </h2>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {calibration.disclosure}
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {calibration.categories.map((item) => (
                  <SummaryCard
                    key={item.category}
                    label={categoryLabels[item.category]}
                    value={
                      item.realisationRate === null
                        ? "Not enough data"
                        : `${item.realisationRate}%`
                    }
                    detail={`${item.realisedWonCount} realised won of ${item.assessedCount} assessed; rate shown from ${calibration.minimumRateSample}.`}
                  />
                ))}
              </div>
            </section>
          ) : null}

          <footer className="text-xs leading-5 text-slate-500">
            Forecast model {forecast.revenueosBaseline.modelVersion}. This
            deterministic view does not use AI, methodology scores, Revenue
            Brain confidence or recommended-action weighting.
          </footer>
        </>
      ) : null}
    </div>
  );
}
