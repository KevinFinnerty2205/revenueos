"use client";

import type {
  SalesActivity,
  SalesFollowOnRate,
  SalesFunnel,
  SalesInsightsMetadata,
  SalesOverview,
  SalesWinLoss,
} from "@revenueos/shared";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { SalesForecast } from "@/components/sales-forecast";
import { SalesTargets, SalesTargetsOverview } from "@/components/sales-targets";

type InsightTab =
  "overview" | "targets" | "forecast" | "funnel" | "activity" | "win-loss";
type InsightPayload =
  SalesOverview | SalesFunnel | SalesActivity | SalesWinLoss;
type Capabilities = { featureFlags: Record<string, boolean> };
type DatePreset =
  | "this-month"
  | "last-month"
  | "this-quarter"
  | "last-quarter"
  | "last-90"
  | "this-year"
  | "custom";

const tabs: Array<{ id: InsightTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "targets", label: "Targets" },
  { id: "forecast", label: "Forecast" },
  { id: "funnel", label: "Funnel" },
  { id: "activity", label: "Activity" },
  { id: "win-loss", label: "Win / loss" },
];

const datePresets: Array<{ id: DatePreset; label: string }> = [
  { id: "this-month", label: "This month" },
  { id: "last-month", label: "Last month" },
  { id: "this-quarter", label: "This quarter" },
  { id: "last-quarter", label: "Last quarter" },
  { id: "last-90", label: "Last 90 days" },
  { id: "this-year", label: "This year" },
  { id: "custom", label: "Custom" },
];

function localDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function rangeFor(
  preset: Exclude<DatePreset, "custom">,
  now = new Date(),
): { startDate: string; endDate: string } {
  const year = now.getFullYear();
  const month = now.getMonth();
  const today = new Date(year, month, now.getDate());
  if (preset === "this-month")
    return {
      startDate: localDate(new Date(year, month, 1)),
      endDate: localDate(today),
    };
  if (preset === "last-month")
    return {
      startDate: localDate(new Date(year, month - 1, 1)),
      endDate: localDate(new Date(year, month, 0)),
    };
  if (preset === "this-year")
    return {
      startDate: localDate(new Date(year, 0, 1)),
      endDate: localDate(today),
    };
  if (preset === "last-90") {
    const start = new Date(today);
    start.setDate(start.getDate() - 89);
    return { startDate: localDate(start), endDate: localDate(today) };
  }
  const quarterStartMonth = Math.floor(month / 3) * 3;
  if (preset === "this-quarter")
    return {
      startDate: localDate(new Date(year, quarterStartMonth, 1)),
      endDate: localDate(today),
    };
  const lastQuarterStart = new Date(year, quarterStartMonth - 3, 1);
  return {
    startDate: localDate(lastQuarterStart),
    endDate: localDate(new Date(year, quarterStartMonth, 0)),
  };
}

function numberValue(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatMetric(value: string | number | null, suffix = ""): string {
  if (value === null) return "Not enough data";
  return `${new Intl.NumberFormat("en-AU", { maximumFractionDigits: 1 }).format(Number(value))}${suffix}`;
}

function formatMoney(amount: string, currency: string): string {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold text-slate-600">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
        {value}
      </p>
      {detail ? (
        <p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p>
      ) : null}
    </article>
  );
}

function ExactTable({
  caption,
  headers,
  rows,
}: {
  caption: string;
  headers: string[];
  rows: Array<Array<string | number>>;
}) {
  return (
    <details className="mt-5 rounded-xl border border-slate-200 bg-white">
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-teal-800 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-teal-600">
        View exact values
      </summary>
      <div className="overflow-x-auto border-t border-slate-200">
        <table className="min-w-full text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              {headers.map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="px-4 py-3 font-semibold"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row, rowIndex) => (
              <tr key={`${caption}-${rowIndex}`}>
                {row.map((cell, cellIndex) => (
                  <td
                    key={`${rowIndex}-${cellIndex}`}
                    className="px-4 py-3 text-slate-700"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function OverviewPanel({
  data,
  onViewTargets,
  targetsEnabled,
}: {
  data: SalesOverview;
  onViewTargets: () => void;
  targetsEnabled: boolean;
}) {
  return (
    <div className="space-y-6">
      {targetsEnabled ? (
        <SalesTargetsOverview onViewAll={onViewTargets} />
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Open opportunities"
          value={formatMetric(data.openOpportunityCount)}
          detail="Current snapshot within the selected owner and pipeline scope."
        />
        <MetricCard
          label="Created"
          value={formatMetric(data.opportunitiesCreatedCount)}
          detail="Opportunities created in the selected local-date range."
        />
        <MetricCard
          label="Win rate"
          value={formatMetric(data.winRate, "%")}
          detail={`${data.wonCount} won · ${data.lostCount} lost`}
        />
        <MetricCard
          label="Median sales cycle"
          value={formatMetric(data.medianSalesCycleDays, " days")}
          detail={`${data.closedCount} currently closed opportunities in range.`}
        />
      </div>
      <section
        aria-labelledby="won-value-title"
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h2
          id="won-value-title"
          className="text-lg font-semibold text-slate-950"
        >
          Won value
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Currencies remain separate; RevenueOS does not apply exchange rates.
        </p>
        {data.wonValues.length ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.wonValues.map((item) => (
              <div key={item.currency} className="rounded-xl bg-teal-50 p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-teal-700">
                  {item.currency}
                </p>
                <p className="mt-1 text-2xl font-semibold text-teal-950">
                  {formatMoney(item.amount, item.currency)}
                </p>
                <p className="mt-1 text-xs text-teal-800">
                  {item.opportunityCount} won
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-5 text-sm text-slate-500">
            No valued won opportunities in this range.
          </p>
        )}
        {data.unvaluedWonCount ? (
          <p className="mt-4 text-xs text-slate-500">
            {data.unvaluedWonCount} won{" "}
            {data.unvaluedWonCount === 1
              ? "opportunity has"
              : "opportunities have"}{" "}
            no value.
          </p>
        ) : null}
      </section>
    </div>
  );
}

function FunnelPanel({ data }: { data: SalesFunnel }) {
  const maximum = Math.max(
    1,
    ...data.stages.map((stage) => stage.enteredCount),
  );
  return (
    <div className="space-y-6">
      <section
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
        aria-labelledby="funnel-title"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2
              id="funnel-title"
              className="text-lg font-semibold text-slate-950"
            >
              {data.pipelineName} progression
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              {data.cohortDefinition}
            </p>
          </div>
          <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-teal-800">
            {data.cohortCount} in cohort
          </span>
        </div>
        <div className="mt-6 space-y-4">
          {data.stages.map((stage) => (
            <div key={stage.stageId}>
              <div className="mb-1.5 flex justify-between gap-4 text-sm">
                <span className="font-semibold text-slate-800">
                  {stage.stageName}
                </span>
                <span className="text-slate-500">
                  {stage.enteredCount} entered ·{" "}
                  {formatMetric(stage.advanceRate, "%")} advanced
                </span>
              </div>
              <div className="h-7 overflow-hidden rounded-lg bg-slate-100">
                <div
                  className="flex h-full min-w-8 items-center justify-end rounded-lg bg-teal-600 pr-2 text-xs font-bold text-white motion-reduce:transition-none"
                  style={{
                    width: `${Math.max(4, (stage.enteredCount / maximum) * 100)}%`,
                  }}
                >
                  {stage.enteredCount}
                </div>
              </div>
            </div>
          ))}
        </div>
        <ExactTable
          caption="Funnel exact values"
          headers={[
            "Stage",
            "Entered",
            "Advanced",
            "Still open",
            "Lost",
            "Advance rate",
          ]}
          rows={data.stages.map((stage) => [
            stage.stageName,
            stage.enteredCount,
            stage.advancedCount,
            stage.stillOpenCount,
            stage.closedLostCount,
            formatMetric(stage.advanceRate, "%"),
          ])}
        />
      </section>
      <section
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
        aria-labelledby="duration-title"
      >
        <h2
          id="duration-title"
          className="text-lg font-semibold text-slate-950"
        >
          Completed stage duration
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Medians use completed, reliable intervals only.
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.stageDurations.map((stage) => (
            <MetricCard
              key={stage.stageId}
              label={stage.stageName}
              value={formatMetric(stage.medianCompletedDays, " days")}
              detail={`${stage.completedIntervalCount} completed intervals`}
            />
          ))}
        </div>
      </section>
      <aside className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <strong>History coverage:</strong> {data.coverage.disclosure}{" "}
        Baseline-only: {data.coverage.baselineOnlyOpportunityCount}; reliable:{" "}
        {data.coverage.reliableOpportunityCount}. Skipped stages are not
        inferred.
      </aside>
    </div>
  );
}

function RateCard({ label, rate }: { label: string; rate: SalesFollowOnRate }) {
  const width = numberValue(rate.rate) ?? 0;
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">{label}</h2>
      <p className="mt-3 text-3xl font-semibold text-slate-950">
        {formatMetric(rate.rate, "%")}
      </p>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-teal-600"
          style={{ width: `${width}%` }}
        />
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-500">
        {rate.followedByOutcomeCount} of {rate.eligibleMatureCount} mature,
        associated records · {rate.immatureCount} awaiting the {rate.windowDays}
        -day window · {rate.excludedUnassociatedCount} unassociated.
      </p>
    </article>
  );
}

function ActivityPanel({ data }: { data: SalesActivity }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <MetricCard
          label="Completed phone calls"
          value={formatMetric(data.phoneCallsCompletedCount)}
        />
        <MetricCard
          label="Completed meetings"
          value={formatMetric(data.meetingsCompletedCount)}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <RateCard
          label="Calls followed by a meeting"
          rate={data.callsFollowedByMeeting}
        />
        <RateCard
          label="Meetings followed by forward progression"
          rate={data.meetingsFollowedByProgression}
        />
        {data.outreachAvailable && data.outreachFollowedByMeeting ? (
          <RateCard
            label="Confirmed live outreach followed by a meeting"
            rate={data.outreachFollowedByMeeting}
          />
        ) : null}
      </div>
      {data.outreachAvailable ? (
        <MetricCard
          label="Confirmed live outreach sent"
          value={formatMetric(data.liveOutreachSentCount)}
          detail="Succeeded live send executions only; drafts, previews, simulations and failed sends are excluded."
        />
      ) : null}
      <aside className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm leading-6 text-sky-950">
        {data.associationDisclosure} These are temporal associations, not causal
        attribution.
      </aside>
    </div>
  );
}

function ReasonBars({
  title,
  reasons,
}: {
  title: string;
  reasons: SalesWinLoss["wonReasons"];
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      {reasons.length ? (
        <div className="mt-5 space-y-4">
          {reasons.map((reason) => (
            <div key={reason.reason}>
              <div className="mb-1.5 flex justify-between text-sm">
                <span className="font-semibold text-slate-800">
                  {reason.label}
                </span>
                <span className="text-slate-500">
                  {reason.count} · {formatMetric(reason.percentage, "%")}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-teal-600"
                  style={{ width: `${numberValue(reason.percentage) ?? 0}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-500">
          No seller-reported reasons in this range.
        </p>
      )}
      <ExactTable
        caption={`${title} exact values`}
        headers={["Reason", "Count", "Share"]}
        rows={reasons.map((reason) => [
          reason.label,
          reason.count,
          formatMetric(reason.percentage, "%"),
        ])}
      />
    </section>
  );
}

function WinLossPanel({ data }: { data: SalesWinLoss }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCard label="Currently won" value={formatMetric(data.wonCount)} />
        <MetricCard
          label="Currently lost"
          value={formatMetric(data.lostCount)}
        />
        <MetricCard
          label="Win rate"
          value={formatMetric(data.winRate, "%")}
          detail="Currently final outcomes with close dates in range."
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ReasonBars title="Why we won" reasons={data.wonReasons} />
        <ReasonBars title="Why we lost" reasons={data.lostReasons} />
      </div>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">
          Loss stage and cycle context
        </h2>
        <ExactTable
          caption="Loss stage and cycle exact values"
          headers={["Measure", "Result", "Sample"]}
          rows={[
            ...data.lossStages.map((stage) => [
              `Lost from ${stage.stageName}`,
              stage.count,
              stage.count,
            ]),
            ...data.salesCycles.map((cycle) => [
              `${cycle.outcome === "won" ? "Won" : "Lost"} median cycle`,
              formatMetric(cycle.medianDays, " days"),
              cycle.sampleSize,
            ]),
          ]}
        />
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">
          Outcome value by currency
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Amounts are grouped by currency and never converted.
        </p>
        <ExactTable
          caption="Outcome values by currency"
          headers={["Outcome", "Currency", "Total", "Median", "Opportunities"]}
          rows={data.values.map((value) => [
            value.outcome === "won" ? "Won" : "Lost",
            value.currency,
            formatMoney(value.amount, value.currency),
            formatMoney(value.medianAmount, value.currency),
            value.opportunityCount,
          ])}
        />
      </section>
      <aside className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm leading-6 text-sky-950">
        Reasons are seller-reported structured fields. Free-text win/loss notes
        are intentionally excluded from analytics.
      </aside>
    </div>
  );
}

export function SalesInsights() {
  const initialRange = rangeFor("this-quarter");
  const [activeTab, setActiveTab] = useState<InsightTab>("overview");
  const [preset, setPreset] = useState<DatePreset>("this-quarter");
  const [startDate, setStartDate] = useState(initialRange.startDate);
  const [endDate, setEndDate] = useState(initialRange.endDate);
  const [pipelineId, setPipelineId] = useState("");
  const [ownerUserId, setOwnerUserId] = useState("");
  const [metadata, setMetadata] = useState<SalesInsightsMetadata | null>(null);
  const [data, setData] = useState<InsightPayload | null>(null);
  const [dataTab, setDataTab] = useState<InsightTab | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [targetsEnabled, setTargetsEnabled] = useState(false);
  const [forecastEnabled, setForecastEnabled] = useState(false);
  const [timezone, setTimezone] = useState(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );
  const [deepLinkApplied, setDeepLinkApplied] = useState(false);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      const query = new URLSearchParams(window.location.search);
      const requestedTab = query.get("tab");
      if (
        requestedTab &&
        requestedTab !== "targets" &&
        tabs.some((tab) => tab.id === requestedTab)
      ) {
        setActiveTab(requestedTab as InsightTab);
      }
      const requestedStart = query.get("startDate");
      const requestedEnd = query.get("endDate");
      if (
        requestedStart?.match(/^\d{4}-\d{2}-\d{2}$/u) &&
        requestedEnd?.match(/^\d{4}-\d{2}-\d{2}$/u)
      ) {
        setPreset("custom");
        setStartDate(requestedStart);
        setEndDate(requestedEnd);
      }
      setPipelineId(query.get("pipelineId") ?? "");
      setOwnerUserId(query.get("ownerUserId") ?? "");
      const requestedTimezone = query.get("timezone");
      if (requestedTimezone) {
        try {
          new Intl.DateTimeFormat("en-AU", { timeZone: requestedTimezone });
          setTimezone(requestedTimezone);
        } catch {
          // Ignore malformed deep-link timezones and retain the browser timezone.
        }
      }
      setDeepLinkApplied(true);
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<Capabilities>("/api/v1/beta/capabilities", {
      signal: controller.signal,
    })
      .then((capabilities) => {
        setTargetsEnabled(capabilities.featureFlags.salesTargets === true);
        setForecastEnabled(capabilities.featureFlags.salesForecasting === true);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setTargetsEnabled(false);
          setForecastEnabled(false);
        }
      });
    apiRequest<SalesInsightsMetadata>("/api/v1/insights/sales/metadata", {
      signal: controller.signal,
    })
      .then(setMetadata)
      .catch((caught: unknown) => {
        if (!controller.signal.aborted)
          setError(
            caught instanceof Error
              ? caught.message
              : "Sales insights could not be loaded.",
          );
      });
    return () => controller.abort();
  }, [retryKey]);

  const loadData = useCallback(
    async (signal: AbortSignal) => {
      if (!deepLinkApplied) return;
      if (activeTab === "targets" || activeTab === "forecast") {
        setData(null);
        setDataTab(null);
        setLoading(false);
        setError(null);
        return;
      }
      if (activeTab === "funnel" && !pipelineId) {
        setData(null);
        setDataTab(null);
        setLoading(false);
        setError(null);
        return;
      }
      setLoading(true);
      setError(null);
      const query = new URLSearchParams({ startDate, endDate, timezone });
      if (pipelineId) query.set("pipelineId", pipelineId);
      if (ownerUserId) query.set("ownerUserId", ownerUserId);
      try {
        const response = await apiRequest<InsightPayload>(
          `/api/v1/insights/sales/${activeTab}?${query.toString()}`,
          { signal },
        );
        setData(response);
        setDataTab(activeTab);
      } catch (caught) {
        if (!signal.aborted)
          setError(
            caught instanceof Error
              ? caught.message
              : "Sales insights could not be loaded.",
          );
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [
      activeTab,
      deepLinkApplied,
      endDate,
      ownerUserId,
      pipelineId,
      startDate,
      timezone,
    ],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      void loadData(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [loadData, retryKey]);

  function changePreset(nextPreset: DatePreset) {
    setPreset(nextPreset);
    if (nextPreset !== "custom") {
      const nextRange = rangeFor(nextPreset);
      setStartDate(nextRange.startDate);
      setEndDate(nextRange.endDate);
    }
  }

  const selectedPipeline = metadata?.pipelines.find(
    (pipeline) => pipeline.id === pipelineId,
  );

  return (
    <div>
      <PageHeader
        eyebrow="Sales analytics"
        title="Sales insights"
        description="A bounded, deterministic view of pipeline progression, activity patterns and seller-reported outcomes."
      />
      {activeTab !== "targets" && activeTab !== "forecast" ? (
        <section
          aria-label="Sales insight filters"
          className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <label className="text-sm font-semibold text-slate-700">
              Date range
              <select
                value={preset}
                onChange={(event) =>
                  changePreset(event.target.value as DatePreset)
                }
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
              >
                {datePresets.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Pipeline
              <select
                value={pipelineId}
                onChange={(event) => setPipelineId(event.target.value)}
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
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
                onChange={(event) => setOwnerUserId(event.target.value)}
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
              >
                <option value="">All owners</option>
                {metadata?.owners.map((owner) => (
                  <option key={owner.userId} value={owner.userId}>
                    {owner.displayName}
                    {owner.active ? "" : " (inactive)"}
                  </option>
                ))}
              </select>
            </label>
            <div className="rounded-xl bg-slate-50 px-3 py-2">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Timezone
              </p>
              <p
                className="mt-2 truncate text-sm font-semibold text-slate-700"
                title={timezone}
              >
                {timezone}
              </p>
            </div>
          </div>
          {preset === "custom" ? (
            <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2">
              <label className="text-sm font-semibold text-slate-700">
                Start date
                <input
                  type="date"
                  value={startDate}
                  max={endDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-slate-300 px-3 py-2 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
                />
              </label>
              <label className="text-sm font-semibold text-slate-700">
                End date
                <input
                  type="date"
                  value={endDate}
                  min={startDate}
                  max={localDate(new Date())}
                  onChange={(event) => setEndDate(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-slate-300 px-3 py-2 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
                />
              </label>
            </div>
          ) : null}
        </section>
      ) : null}
      <div
        role="tablist"
        aria-label="Sales insight sections"
        className="mb-6 flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1"
      >
        {tabs
          .filter(
            (tab) =>
              (tab.id !== "targets" || targetsEnabled) &&
              (tab.id !== "forecast" || forecastEnabled),
          )
          .map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`min-h-11 whitespace-nowrap rounded-lg px-4 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-teal-600 ${activeTab === tab.id ? "bg-white text-teal-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
            >
              {tab.label}
            </button>
          ))}
      </div>
      {activeTab === "funnel" && !pipelineId ? (
        <section className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
          <h2 className="text-lg font-semibold text-slate-900">
            Choose one pipeline to view its funnel
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Stage orders are pipeline-specific, so funnels are never combined
            across pipelines.
          </p>
        </section>
      ) : null}
      {activeTab === "targets" ? <SalesTargets /> : null}
      {activeTab === "forecast" ? <SalesForecast /> : null}
      {loading && activeTab !== "forecast" ? (
        <div
          role="status"
          className="rounded-2xl border border-slate-200 bg-white px-6 py-14 text-center text-sm font-semibold text-slate-600"
        >
          Loading sales insights…
        </div>
      ) : null}
      {error && activeTab !== "forecast" ? (
        <div
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-950"
        >
          <p className="font-semibold">Sales insights are unavailable</p>
          <p className="mt-1 text-sm">{error}</p>
          <button
            type="button"
            onClick={() => setRetryKey((value) => value + 1)}
            className="mt-4 rounded-lg bg-red-900 px-4 py-2 text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-red-700 focus:ring-offset-2"
          >
            Try again
          </button>
        </div>
      ) : null}
      {!loading && !error && data && dataTab === "overview" ? (
        <OverviewPanel
          data={data as SalesOverview}
          onViewTargets={() => setActiveTab("targets")}
          targetsEnabled={targetsEnabled}
        />
      ) : null}
      {!loading && !error && data && dataTab === "funnel" ? (
        <FunnelPanel data={data as SalesFunnel} />
      ) : null}
      {!loading && !error && data && dataTab === "activity" ? (
        <ActivityPanel data={data as SalesActivity} />
      ) : null}
      {!loading && !error && data && dataTab === "win-loss" ? (
        <WinLossPanel data={data as SalesWinLoss} />
      ) : null}
      {!loading &&
      !error &&
      data &&
      dataTab === "overview" &&
      !(data as SalesOverview).hasOpportunities ? (
        <p className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
          No opportunities matched this period. Try a wider range or remove an
          owner or pipeline filter.
        </p>
      ) : null}
      {activeTab !== "targets" && activeTab !== "forecast" ? (
        <footer className="mt-8 text-xs leading-5 text-slate-500">
          Inclusive local dates: {startDate} to {endDate}.{" "}
          {selectedPipeline
            ? `Pipeline: ${selectedPipeline.name}. `
            : "All pipelines. "}
          Definitions use canonical RevenueOS records and metric catalogue
          version 1.
        </footer>
      ) : null}
    </div>
  );
}
