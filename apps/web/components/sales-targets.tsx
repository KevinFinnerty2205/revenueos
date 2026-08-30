"use client";

import type {
  SalesTarget,
  SalesTargetCategory,
  SalesTargetList,
  SalesTargetMetadata,
  SalesTargetMetricPolicy,
  SalesTargetPeriodType,
} from "@revenueos/shared";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "@/lib/api";

type TargetView = "current" | "past" | "archived";
type TargetKind = "self" | "assigned" | "organisation";

const categoryLabels: Record<SalesTargetCategory, string> = {
  outcome: "Outcomes",
  pipeline_development: "Pipeline development",
  activity: "Activity",
};
const opportunityMetricIds = new Set([
  "won_value",
  "opportunities_closed_won_count",
  "opportunities_created_count",
]);

function localDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function currentMonth(): string {
  return localDate(new Date()).slice(0, 7);
}

function periodOptions(type: SalesTargetPeriodType) {
  const now = new Date();
  if (type === "quarter") {
    const currentQuarterMonth = Math.floor(now.getMonth() / 3) * 3;
    return Array.from({ length: 12 }, (_, offset) => {
      const start = new Date(
        now.getFullYear(),
        currentQuarterMonth + offset * 3,
        1,
      );
      const quarter = Math.floor(start.getMonth() / 3) + 1;
      return {
        value: localDate(start),
        label: `Q${quarter} ${start.getFullYear()}`,
      };
    });
  }
  return Array.from({ length: 6 }, (_, offset) => {
    const year = now.getFullYear() + offset;
    return { value: `${year}-01-01`, label: String(year) };
  });
}

function formatNumber(value: string): string {
  return new Intl.NumberFormat("en-AU", { maximumFractionDigits: 2 }).format(
    Number(value),
  );
}

function formatValue(target: SalesTarget, value: string | null): string {
  if (value === null) return "Unavailable";
  if (target.metric.unit === "currency" && target.currency) {
    return new Intl.NumberFormat("en-AU", {
      style: "currency",
      currency: target.currency,
      maximumFractionDigits: 2,
    }).format(Number(value));
  }
  return formatNumber(value);
}

function targetLabel(target: SalesTarget): string {
  if (target.scope === "organisation") return "Organisation target";
  if (target.origin === "admin_assigned") return "Assigned target";
  return "Personal goal";
}

function targetInsightsHref(target: SalesTarget): string | null {
  if (!target.progress.calculatedThrough) return null;
  const query = new URLSearchParams({
    tab: target.metric.category === "activity" ? "activity" : "overview",
    metric: target.metric.metricId,
    startDate: target.periodStart,
    endDate: target.progress.calculatedThrough,
    timezone: target.timezone,
  });
  if (target.pipelineId) query.set("pipelineId", target.pipelineId);
  if (target.scope === "personal" && target.ownerUserId) {
    query.set("ownerUserId", target.ownerUserId);
  }
  return `/insights?${query.toString()}`;
}

function targetDisplayOrder(left: SalesTarget, right: SalesTarget): number {
  return (
    left.metric.displayOrder - right.metric.displayOrder ||
    left.periodStart.localeCompare(right.periodStart) ||
    left.id.localeCompare(right.id)
  );
}

function TargetCard({
  target,
  onView,
  onRevise,
  onArchive,
}: {
  target: SalesTarget;
  onView: (target: SalesTarget) => void;
  onRevise: (target: SalesTarget) => void;
  onArchive: (target: SalesTarget) => void;
}) {
  const isActivity = target.metric.category === "activity";
  const percentage = Number(target.progress.percentageComplete ?? 0);
  const displayPercentage = target.progress.percentageComplete
    ? `${formatNumber(target.progress.percentageComplete)}%`
    : target.progress.state === "upcoming"
      ? "Starts soon"
      : "Unavailable";
  return (
    <article
      className={`rounded-2xl border p-5 shadow-sm ${isActivity ? "border-slate-200 bg-slate-50/60" : "border-teal-100 bg-white"}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-teal-700">
            {targetLabel(target)} · {categoryLabels[target.metric.category]}
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {target.metric.label}
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            {target.periodLabel}
            {target.pipelineName
              ? ` · ${target.pipelineName}`
              : " · All pipelines"}
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold capitalize text-slate-700">
          {target.status}
        </span>
      </div>
      {target.progress.state === "available" ? (
        <>
          <p className="mt-5 text-2xl font-semibold tracking-tight text-slate-950">
            {formatValue(target, target.progress.actualValue)}
            <span className="text-base font-medium text-slate-500">
              {" "}
              of {formatValue(target, target.progress.targetValue)}
            </span>
          </p>
          <div
            className="mt-4 h-2.5 overflow-hidden rounded-full bg-slate-100"
            role="progressbar"
            aria-label={`${target.metric.label}: ${displayPercentage} complete`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.min(100, Math.max(0, percentage))}
          >
            <div
              className={`h-full rounded-full motion-reduce:transition-none ${isActivity ? "bg-slate-500" : "bg-teal-600"}`}
              style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
            />
          </div>
          <div className="mt-3 flex flex-wrap justify-between gap-2 text-sm">
            <span className="font-semibold text-slate-800">
              {displayPercentage}
            </span>
            <span className="text-slate-600">
              {target.progress.targetReached
                ? `${formatValue(target, target.progress.aboveTargetValue)} above target`
                : `${formatValue(target, target.progress.remainingValue)} remaining`}
            </span>
          </div>
        </>
      ) : (
        <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
          {target.progress.state === "upcoming"
            ? `Starts ${target.periodStart}. No actual has been invented for this future period.`
            : "Canonical Sales Analytics progress is currently unavailable."}
        </div>
      )}
      <p className="mt-3 text-xs text-slate-500">
        {target.origin === "admin_assigned"
          ? `Set by ${target.createdByDisplayName}`
          : "Set by you"}
        {target.scope === "personal" && target.ownerDisplayName
          ? ` · For ${target.ownerDisplayName}`
          : ""}
      </p>
      <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
        <button
          type="button"
          onClick={() => onView(target)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-600"
        >
          View details
        </button>
        {target.canRevise ? (
          <button
            type="button"
            onClick={() => onRevise(target)}
            className="rounded-lg border border-teal-700 px-3 py-2 text-sm font-semibold text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600"
          >
            Change target
          </button>
        ) : null}
        {target.canArchive ? (
          <button
            type="button"
            onClick={() => onArchive(target)}
            className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-600"
          >
            Archive
          </button>
        ) : null}
      </div>
    </article>
  );
}

function TargetDetail({
  target,
  onClose,
}: {
  target: SalesTarget;
  onClose: () => void;
}) {
  const insightsHref = targetInsightsHref(target);
  return (
    <section
      role="dialog"
      aria-modal="true"
      aria-labelledby="target-detail-title"
      className="mb-6 rounded-2xl border-2 border-teal-200 bg-white p-5 shadow-lg"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-teal-700">
            {targetLabel(target)}
          </p>
          <h2
            id="target-detail-title"
            className="mt-1 text-xl font-semibold text-slate-950"
          >
            {target.metric.label} · {target.periodLabel}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 focus:outline-none focus:ring-2 focus:ring-teal-600"
        >
          Close
        </button>
      </div>
      <dl className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Actual", formatValue(target, target.progress.actualValue)],
          ["Goal", formatValue(target, target.latestRevision.goalValue)],
          ["Remaining", formatValue(target, target.progress.remainingValue)],
          [
            "Progress",
            target.progress.percentageComplete
              ? `${formatNumber(target.progress.percentageComplete)}%`
              : "Unavailable",
          ],
        ].map(([term, value]) => (
          <div key={term} className="rounded-xl bg-slate-50 p-4">
            <dt className="text-xs font-bold uppercase tracking-wider text-slate-500">
              {term}
            </dt>
            <dd className="mt-1 text-lg font-semibold text-slate-950">
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="font-semibold text-slate-900">
            How this is calculated
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {target.metric.description} Metric definition{" "}
            {target.metric.definitionVersion}. {target.metric.dateSemantics}
          </p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
            {target.progress.disclosures.map((item) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
          {insightsHref ? (
            <a
              href={insightsHref}
              className="mt-4 inline-block text-sm font-semibold text-teal-800 underline-offset-4 hover:underline focus:outline-none focus:ring-2 focus:ring-teal-600"
            >
              View this metric in Insights
            </a>
          ) : null}
        </div>
        <div>
          <h3 className="font-semibold text-slate-900">Target history</h3>
          <ol className="mt-3 space-y-3">
            {target.revisions.map((revision) => (
              <li
                key={revision.id}
                className="rounded-xl border border-slate-200 p-3 text-sm text-slate-600"
              >
                <span className="font-semibold text-slate-900">
                  {formatValue(target, revision.goalValue)}
                </span>{" "}
                · revision {revision.revisionNumber} ·{" "}
                {revision.createdByDisplayName} ·{" "}
                {new Intl.DateTimeFormat("en-AU", {
                  dateStyle: "medium",
                }).format(new Date(revision.createdAt))}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

export function SalesTargetsOverview({ onViewAll }: { onViewAll: () => void }) {
  const [metadata, setMetadata] = useState<SalesTargetMetadata | null>(null);
  const [targets, setTargets] = useState<SalesTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<SalesTargetMetadata>("/api/v1/targets/metadata", {
        signal: controller.signal,
      }),
      apiRequest<SalesTargetList>("/api/v1/targets?view=current", {
        signal: controller.signal,
      }),
    ])
      .then(([nextMetadata, list]) => {
        setMetadata(nextMetadata);
        setTargets(list.items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setUnavailable(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const visibleTargets = targets
    .filter(
      (target) =>
        target.scope === "organisation" ||
        target.ownerUserId === metadata?.currentUserId,
    )
    .sort((left, right) => {
      if (left.scope !== right.scope) return left.scope === "personal" ? -1 : 1;
      return left.metric.displayOrder - right.metric.displayOrder;
    })
    .slice(0, 5);

  if (unavailable) return null;

  return (
    <section
      aria-labelledby="active-targets-title"
      className="rounded-2xl border border-teal-200 bg-teal-50/60 p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="active-targets-title"
            className="text-lg font-semibold text-slate-950"
          >
            Active targets
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Your personal and shared organisation goals, using canonical Sales
            Insights actuals.
          </p>
        </div>
        <button
          type="button"
          onClick={onViewAll}
          className="rounded-lg border border-teal-700 px-3 py-2 text-sm font-semibold text-teal-900 focus:outline-none focus:ring-2 focus:ring-teal-600"
        >
          {visibleTargets.length ? "View all targets" : "Set a target"}
        </button>
      </div>
      {loading ? (
        <p role="status" className="mt-5 text-sm text-slate-600">
          Loading active targets…
        </p>
      ) : visibleTargets.length ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visibleTargets.map((target) => (
            <article
              key={target.id}
              className="rounded-xl border border-teal-100 bg-white p-4"
            >
              <p className="text-xs font-bold uppercase tracking-wider text-teal-700">
                {targetLabel(target)} · {target.periodLabel}
              </p>
              <h3 className="mt-1 font-semibold text-slate-950">
                {target.metric.label}
              </h3>
              <p className="mt-3 text-xl font-semibold text-slate-950">
                {target.progress.state === "available"
                  ? `${formatValue(target, target.progress.actualValue)} / ${formatValue(target, target.latestRevision.goalValue)}`
                  : target.progress.state === "upcoming"
                    ? "Upcoming"
                    : "Actual unavailable"}
              </p>
              {target.progress.percentageComplete ? (
                <p className="mt-1 text-sm font-semibold text-slate-600">
                  {formatNumber(target.progress.percentageComplete)}% complete
                </p>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-5 text-sm text-slate-600">
          No personal or organisation targets are active in the current period.
        </p>
      )}
    </section>
  );
}

export function SalesTargets() {
  const [metadata, setMetadata] = useState<SalesTargetMetadata | null>(null);
  const [targets, setTargets] = useState<SalesTarget[]>([]);
  const [view, setView] = useState<TargetView>("current");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [kind, setKind] = useState<TargetKind>("self");
  const [metricId, setMetricId] = useState("");
  const [ownerUserId, setOwnerUserId] = useState("");
  const [pipelineId, setPipelineId] = useState("");
  const [periodType, setPeriodType] = useState<SalesTargetPeriodType>("month");
  const [monthAnchor, setMonthAnchor] = useState(currentMonth());
  const [controlledAnchor, setControlledAnchor] = useState("");
  const [goalValue, setGoalValue] = useState("");
  const [currency, setCurrency] = useState("AUD");
  const [submitting, setSubmitting] = useState(false);
  const [detail, setDetail] = useState<SalesTarget | null>(null);
  const [revisionTarget, setRevisionTarget] = useState<SalesTarget | null>(
    null,
  );
  const [revisionValue, setRevisionValue] = useState("");
  const [archiveTarget, setArchiveTarget] = useState<SalesTarget | null>(null);

  const load = useCallback(async (targetView: TargetView) => {
    setLoading(true);
    setError(null);
    try {
      const [nextMetadata, list] = await Promise.all([
        apiRequest<SalesTargetMetadata>("/api/v1/targets/metadata"),
        apiRequest<SalesTargetList>(`/api/v1/targets?view=${targetView}`),
      ]);
      setMetadata(nextMetadata);
      setTargets(list.items);
      setMetricId(
        (current) => current || nextMetadata.metrics[0]?.metricId || "",
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Targets could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void load(view);
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [load, view]);

  const selectedMetric =
    metadata?.metrics.find((metric) => metric.metricId === metricId) ?? null;
  const quarterOrYearOptions = useMemo(
    () => periodOptions(periodType),
    [periodType],
  );

  const ownTargets = targets
    .filter(
      (target) =>
        target.scope === "personal" &&
        target.ownerUserId === metadata?.currentUserId,
    )
    .sort(targetDisplayOrder);
  const organisationTargets = targets
    .filter((target) => target.scope === "organisation")
    .sort(targetDisplayOrder);
  const managedTargets = targets.filter(
    (target) =>
      target.scope === "personal" &&
      target.ownerUserId !== metadata?.currentUserId &&
      target.origin === "admin_assigned",
  );
  const peerSelfSetTargets = targets.filter(
    (target) =>
      target.scope === "personal" &&
      target.ownerUserId !== metadata?.currentUserId &&
      target.origin === "self_set",
  );

  async function submitTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!metadata || !selectedMetric) return;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    const scope = kind === "organisation" ? "organisation" : "personal";
    const origin = kind === "self" ? "self_set" : "admin_assigned";
    const periodAnchor =
      periodType === "month" ? `${monthAnchor}-01` : controlledAnchor;
    const body = {
      metricId: selectedMetric.metricId,
      metricDefinitionVersion: selectedMetric.definitionVersion,
      scope,
      origin,
      ownerUserId:
        kind === "assigned"
          ? ownerUserId
          : kind === "self"
            ? metadata.currentUserId
            : null,
      pipelineId:
        opportunityMetricIds.has(selectedMetric.metricId) && pipelineId
          ? pipelineId
          : null,
      periodType,
      periodAnchor,
      goalValue,
      currency: selectedMetric.requiresCurrency ? currency.toUpperCase() : null,
    };
    try {
      await apiRequest<SalesTarget>("/api/v1/targets", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setShowForm(false);
      setGoalValue("");
      setNotice(
        "Target set. Actual progress is calculated from Sales Analytics.",
      );
      setView("current");
      await load("current");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The target could not be set.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function openDetail(target: SalesTarget) {
    try {
      setDetail(await apiRequest<SalesTarget>(`/api/v1/targets/${target.id}`));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Target details could not be loaded.",
      );
    }
  }

  async function submitRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!revisionTarget) return;
    setSubmitting(true);
    try {
      const revised = await apiRequest<SalesTarget>(
        `/api/v1/targets/${revisionTarget.id}/revisions`,
        {
          method: "POST",
          body: JSON.stringify({
            goalValue: revisionValue,
            expectedRevisionNumber:
              revisionTarget.latestRevision.revisionNumber,
          }),
        },
      );
      setRevisionTarget(null);
      setDetail(revised);
      setNotice("Target changed. The previous value remains in history.");
      await load(view);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The target could not be changed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmArchive() {
    if (!archiveTarget) return;
    setSubmitting(true);
    try {
      await apiRequest(`/api/v1/targets/${archiveTarget.id}/archive`, {
        method: "POST",
        body: JSON.stringify({ confirmed: true }),
      });
      setArchiveTarget(null);
      setNotice(
        "Target archived. Its configuration and revision history are retained.",
      );
      await load(view);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The target could not be archived.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !metadata) {
    return (
      <div
        role="status"
        className="rounded-2xl border border-slate-200 bg-white p-10 text-center"
      >
        Loading targets…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">Targets</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
            Compare a human-set goal with the exact canonical metrics used in
            Sales Insights. Targets do not predict outcomes or rank people.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((value) => !value)}
          className="rounded-xl bg-teal-800 px-4 py-2.5 text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
        >
          {showForm ? "Cancel" : "Set target"}
        </button>
      </div>

      {notice ? (
        <p
          role="status"
          className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-950"
        >
          {notice}
        </p>
      ) : null}
      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-950"
        >
          {error}
        </div>
      ) : null}

      {showForm && metadata ? (
        <form
          onSubmit={submitTarget}
          className="rounded-2xl border border-teal-200 bg-white p-5 shadow-sm"
        >
          <h3 className="text-lg font-semibold text-slate-950">Set target</h3>
          <p className="mt-1 text-sm text-slate-600">
            Choose a supported metric, calendar period and goal. RevenueOS
            supplies the actual.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="text-sm font-semibold text-slate-700">
              What do you want to achieve?
              <select
                value={metricId}
                onChange={(event) => {
                  const nextMetricId = event.target.value;
                  setMetricId(nextMetricId);
                  if (!opportunityMetricIds.has(nextMetricId))
                    setPipelineId("");
                }}
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
              >
                {(["outcome", "pipeline_development", "activity"] as const).map(
                  (category) => (
                    <optgroup key={category} label={categoryLabels[category]}>
                      {metadata.metrics
                        .filter((metric) => metric.category === category)
                        .map((metric) => (
                          <option key={metric.metricId} value={metric.metricId}>
                            {metric.label}
                          </option>
                        ))}
                    </optgroup>
                  ),
                )}
              </select>
            </label>
            {metadata.canAssignPersonalTargets ? (
              <label className="text-sm font-semibold text-slate-700">
                Who is this for?
                <select
                  value={kind}
                  onChange={(event) =>
                    setKind(event.target.value as TargetKind)
                  }
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
                >
                  <option value="self">My personal goal</option>
                  <option value="assigned">A salesperson · assigned</option>
                  <option value="organisation">Organisation</option>
                </select>
              </label>
            ) : null}
            {kind === "assigned" ? (
              <label className="text-sm font-semibold text-slate-700">
                Salesperson
                <select
                  required
                  value={ownerUserId}
                  onChange={(event) => setOwnerUserId(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
                >
                  <option value="">Choose a salesperson</option>
                  {metadata.owners.map((owner) => (
                    <option key={owner.userId} value={owner.userId}>
                      {owner.displayName}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label className="text-sm font-semibold text-slate-700">
              Period
              <select
                value={periodType}
                onChange={(event) => {
                  const nextPeriodType = event.target
                    .value as SalesTargetPeriodType;
                  setPeriodType(nextPeriodType);
                  if (nextPeriodType !== "month") {
                    setControlledAnchor(
                      periodOptions(nextPeriodType)[0]?.value ?? "",
                    );
                  }
                }}
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
              >
                <option value="month">Monthly</option>
                <option value="quarter">Quarterly</option>
                <option value="year">Annual</option>
              </select>
            </label>
            {periodType === "month" ? (
              <label className="text-sm font-semibold text-slate-700">
                Month
                <input
                  required
                  type="month"
                  min={currentMonth()}
                  value={monthAnchor}
                  onChange={(event) => setMonthAnchor(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-slate-300 px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
                />
              </label>
            ) : (
              <label className="text-sm font-semibold text-slate-700">
                {periodType === "quarter" ? "Quarter" : "Year"}
                <select
                  value={controlledAnchor}
                  onChange={(event) => setControlledAnchor(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
                >
                  {quarterOrYearOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {selectedMetric &&
            opportunityMetricIds.has(selectedMetric.metricId) ? (
              <label className="text-sm font-semibold text-slate-700">
                Pipeline{" "}
                <span className="font-normal text-slate-500">(optional)</span>
                <select
                  value={pipelineId}
                  onChange={(event) => setPipelineId(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
                >
                  <option value="">All pipelines</option>
                  {metadata.pipelines
                    .filter((pipeline) => pipeline.active)
                    .map((pipeline) => (
                      <option key={pipeline.id} value={pipeline.id}>
                        {pipeline.name}
                      </option>
                    ))}
                </select>
              </label>
            ) : null}
            {selectedMetric?.requiresCurrency ? (
              <label className="text-sm font-semibold text-slate-700">
                ISO currency
                <input
                  required
                  value={currency}
                  minLength={3}
                  maxLength={3}
                  pattern="[A-Za-z]{3}"
                  onChange={(event) => setCurrency(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-slate-300 px-3 py-2.5 uppercase focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
                />
              </label>
            ) : null}
            <label className="text-sm font-semibold text-slate-700">
              Goal
              <input
                required
                inputMode="decimal"
                pattern="(0|[1-9][0-9]*)(\.[0-9]{1,2})?"
                value={goalValue}
                onChange={(event) => setGoalValue(event.target.value)}
                placeholder={
                  selectedMetric?.unit === "currency" ? "20000" : "12"
                }
                className="mt-2 block w-full rounded-xl border border-slate-300 px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
              />
            </label>
          </div>
          <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
            <strong className="text-slate-800">{selectedMetric?.label}:</strong>{" "}
            {selectedMetric?.description} Period boundaries use{" "}
            {metadata.organisationTimezone}.{" "}
            {selectedMetric?.category === "activity"
              ? "This is an activity target; more activity does not by itself mean better sales performance."
              : ""}
          </div>
          <button
            disabled={submitting}
            type="submit"
            className="mt-5 rounded-xl bg-teal-800 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
          >
            {submitting ? "Setting target…" : "Set target"}
          </button>
        </form>
      ) : null}

      {revisionTarget ? (
        <form
          onSubmit={submitRevision}
          role="dialog"
          aria-modal="true"
          aria-labelledby="revise-target-title"
          className="rounded-2xl border-2 border-amber-200 bg-amber-50 p-5"
        >
          <h3 id="revise-target-title" className="font-semibold text-amber-950">
            Change {revisionTarget.periodLabel} target?
          </h3>
          <p className="mt-2 text-sm text-amber-900">
            The earlier target of{" "}
            {formatValue(
              revisionTarget,
              revisionTarget.latestRevision.goalValue,
            )}{" "}
            will remain in history.
          </p>
          <label className="mt-4 block text-sm font-semibold text-amber-950">
            New target
            <input
              autoFocus
              required
              value={revisionValue}
              onChange={(event) => setRevisionValue(event.target.value)}
              className="mt-2 block w-full max-w-xs rounded-lg border border-amber-300 px-3 py-2"
            />
          </label>
          <div className="mt-4 flex gap-2">
            <button
              disabled={submitting}
              className="rounded-lg bg-amber-900 px-4 py-2 text-sm font-semibold text-white"
            >
              Confirm change
            </button>
            <button
              type="button"
              onClick={() => setRevisionTarget(null)}
              className="rounded-lg px-4 py-2 text-sm font-semibold text-amber-900"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      {archiveTarget ? (
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="archive-target-title"
          className="rounded-2xl border-2 border-slate-300 bg-white p-5"
        >
          <h3
            id="archive-target-title"
            className="font-semibold text-slate-950"
          >
            Archive this target?
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            It will leave the active view, but its identity and revision history
            will be retained.
          </p>
          <div className="mt-4 flex gap-2">
            <button
              disabled={submitting}
              type="button"
              onClick={() => void confirmArchive()}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
            >
              Archive target
            </button>
            <button
              type="button"
              onClick={() => setArchiveTarget(null)}
              className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
          </div>
        </section>
      ) : null}

      {detail ? (
        <TargetDetail target={detail} onClose={() => setDetail(null)} />
      ) : null}

      <div
        role="tablist"
        aria-label="Target periods"
        className="flex w-fit gap-1 rounded-xl bg-slate-100 p-1"
      >
        {(["current", "past", "archived"] as const).map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={view === item}
            onClick={() => setView(item)}
            className={`min-h-11 rounded-lg px-4 text-sm font-semibold capitalize focus:outline-none focus:ring-2 focus:ring-teal-600 ${view === item ? "bg-white text-teal-900 shadow-sm" : "text-slate-600"}`}
          >
            {item}
          </button>
        ))}
      </div>

      {!loading && targets.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <h3 className="text-lg font-semibold text-slate-900">
            {view === "current" ? "No targets yet" : `No ${view} targets`}
          </h3>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
            Targets compare a chosen sales goal with the same metrics used in
            Insights. Nothing is forecast or ranked.
          </p>
          {view === "current" ? (
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="mt-5 rounded-xl bg-teal-800 px-4 py-2.5 text-sm font-semibold text-white"
            >
              Set a target
            </button>
          ) : null}
        </section>
      ) : null}

      {ownTargets.length ? (
        <section aria-labelledby="my-targets-title">
          <h3
            id="my-targets-title"
            className="mb-3 text-lg font-semibold text-slate-950"
          >
            My targets
          </h3>
          <div className="grid gap-4 lg:grid-cols-2">
            {ownTargets.map((target) => (
              <TargetCard
                key={target.id}
                target={target}
                onView={(item) => void openDetail(item)}
                onRevise={(item) => {
                  setRevisionTarget(item);
                  setRevisionValue(item.latestRevision.goalValue);
                }}
                onArchive={setArchiveTarget}
              />
            ))}
          </div>
        </section>
      ) : null}
      {organisationTargets.length ? (
        <section aria-labelledby="organisation-targets-title">
          <h3
            id="organisation-targets-title"
            className="mb-3 text-lg font-semibold text-slate-950"
          >
            Organisation targets
          </h3>
          <p className="mb-3 text-sm text-slate-600">
            Shared progress only. Individual contribution is intentionally not
            shown.
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            {organisationTargets.map((target) => (
              <TargetCard
                key={target.id}
                target={target}
                onView={(item) => void openDetail(item)}
                onRevise={(item) => {
                  setRevisionTarget(item);
                  setRevisionValue(item.latestRevision.goalValue);
                }}
                onArchive={setArchiveTarget}
              />
            ))}
          </div>
        </section>
      ) : null}
      {managedTargets.length ? (
        <section
          aria-labelledby="managed-targets-title"
          className="rounded-2xl border border-slate-200 bg-white p-5"
        >
          <h3
            id="managed-targets-title"
            className="text-lg font-semibold text-slate-950"
          >
            Manage assigned targets
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Configuration is sorted by person and period—never by attainment.
          </p>
          <ul className="mt-4 divide-y divide-slate-100">
            {[...managedTargets]
              .sort((a, b) =>
                (a.ownerDisplayName ?? "").localeCompare(
                  b.ownerDisplayName ?? "",
                ),
              )
              .map((target) => (
                <li
                  key={target.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-3"
                >
                  <span className="text-sm text-slate-700">
                    <strong className="text-slate-950">
                      {target.ownerDisplayName}
                    </strong>{" "}
                    · {target.metric.label} ·{" "}
                    {formatValue(target, target.latestRevision.goalValue)} ·{" "}
                    {target.periodLabel}
                  </span>
                  <button
                    type="button"
                    onClick={() => void openDetail(target)}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-600"
                  >
                    Open
                  </button>
                </li>
              ))}
          </ul>
        </section>
      ) : null}
      {peerSelfSetTargets.length ? (
        <section
          aria-labelledby="peer-self-targets-title"
          className="rounded-2xl border border-slate-200 bg-white p-5"
        >
          <h3
            id="peer-self-targets-title"
            className="text-lg font-semibold text-slate-950"
          >
            Personal goals · read-only
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Administrators can inspect these goals but cannot change or archive
            them.
          </p>
          <ul className="mt-4 divide-y divide-slate-100">
            {[...peerSelfSetTargets]
              .sort((a, b) =>
                (a.ownerDisplayName ?? "").localeCompare(
                  b.ownerDisplayName ?? "",
                ),
              )
              .map((target) => (
                <li key={target.id} className="py-3 text-sm text-slate-700">
                  <strong className="text-slate-950">
                    {target.ownerDisplayName}
                  </strong>{" "}
                  · {target.metric.label} ·{" "}
                  {formatValue(target, target.latestRevision.goalValue)} ·{" "}
                  {target.periodLabel}
                </li>
              ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
