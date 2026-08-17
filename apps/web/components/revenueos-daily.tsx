"use client";

import type {
  DailyAction,
  DailyDealAttention,
  DailyInteraction,
  DailyPipelineSummary,
  DailyPriority,
  DailyRecommendation,
  DailyResponse,
} from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

export function RevenueOSDaily() {
  const [daily, setDaily] = useState<DailyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(false);
    setRefreshKey((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    const parameters = new URLSearchParams({ timezone });
    apiRequest<DailyResponse>(`/api/v1/daily?${parameters.toString()}`, {
      signal: controller.signal,
    })
      .then((response) => {
        setDaily(response);
        setError(false);
      })
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [refreshKey]);

  useEffect(() => {
    const onFocus = () => refresh();
    window.addEventListener("focus", onFocus);
    const current = new Date();
    const nextDay = new Date(
      current.getFullYear(),
      current.getMonth(),
      current.getDate() + 1,
      0,
      0,
      2,
    );
    const midnightRefresh = window.setTimeout(
      refresh,
      Math.max(1_000, nextDay.getTime() - current.getTime()),
    );
    return () => {
      window.removeEventListener("focus", onFocus);
      window.clearTimeout(midnightRefresh);
    };
  }, [refresh]);

  if (loading && daily === null) return <DailyLoading />;
  if (error && daily === null) return <DailyError onRetry={refresh} />;
  if (daily === null) return null;

  const firstName = daily.userDisplayName.split(/\s/u)[0] || "there";
  const mobilePriorityIsNext =
    daily.nextInteraction !== null &&
    daily.topPriority?.sourceId === daily.nextInteraction.id;

  return (
    <section aria-labelledby="daily-title">
      <header className="mb-7 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Home · RevenueOS Daily
          </p>
          <h1
            id="daily-title"
            className="mt-3 text-4xl font-semibold tracking-[-0.03em] text-slate-950 sm:text-5xl"
          >
            {greeting()}, {firstName}
          </h1>
          <p className="mt-3 text-base text-slate-600">
            {formatLocalDate(daily.localDate)} · What matters today
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link className="secondary-button" href="/assistant">
            Search
          </Link>
          <p className="hidden text-xs text-slate-500 sm:block">
            Updated {formatUpdated(daily.generatedAt)}
          </p>
        </div>
      </header>

      {error ? (
        <div
          role="status"
          className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
        >
          <span>Your last loaded day is still shown.</span>
          <button
            className="font-bold underline"
            type="button"
            onClick={refresh}
          >
            Refresh
          </button>
        </div>
      ) : null}

      {!daily.hasOpportunities ? <NewUserWelcome /> : null}

      {daily.hasOpportunities && daily.nextInteraction ? (
        <div className="mb-5 lg:hidden">
          <MobileNextInteraction
            interaction={daily.nextInteraction}
            timezone={daily.timezone}
          />
        </div>
      ) : null}

      {daily.hasOpportunities && daily.topPriority ? (
        <div className={mobilePriorityIsNext ? "hidden lg:block" : "block"}>
          <PriorityCard
            priority={daily.topPriority}
            timezone={daily.timezone}
          />
        </div>
      ) : daily.hasOpportunities && daily.caughtUp ? (
        <CaughtUp />
      ) : null}

      {daily.hasOpportunities ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(17rem,0.75fr)] lg:items-start">
          <div className="grid gap-6">
            <div className="hidden lg:block">
              <InteractionsSection
                interactions={daily.todayInteractions}
                total={daily.totalTodayInteractions}
                available={daily.availability.interactions}
                timezone={daily.timezone}
              />
            </div>
            <ActionsSection
              actions={daily.actions.items}
              count={daily.actions.attentionCount}
              overdueCount={daily.actions.overdueCount}
              available={daily.availability.actions}
              timezone={daily.timezone}
            />
            <DealsSection
              deals={daily.dealAttention.items}
              count={daily.dealAttention.attentionCount}
              available={daily.availability.dealAttention}
            />
            <div className="lg:hidden">
              <MobileDaySummary
                interactions={daily.todayInteractions}
                total={daily.totalTodayInteractions}
                available={daily.availability.interactions}
                timezone={daily.timezone}
                primaryInteractionId={daily.nextInteraction?.id ?? null}
              />
            </div>
          </div>
          <aside aria-label="Daily context" className="grid gap-6">
            <PipelineCard
              pipeline={daily.pipeline}
              available={daily.availability.pipeline}
            />
            <RecommendationsCard
              recommendations={daily.recommendations}
              available={daily.availability.recommendations}
            />
          </aside>
        </div>
      ) : null}
    </section>
  );
}

function DailyLoading() {
  return (
    <section aria-labelledby="daily-loading-title" aria-busy="true">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
        Home · RevenueOS Daily
      </p>
      <h1
        id="daily-loading-title"
        className="mt-3 text-4xl font-semibold text-slate-950"
      >
        Loading your day…
      </h1>
      <div className="mt-7 h-56 animate-pulse rounded-[2rem] bg-slate-200 motion-reduce:animate-none" />
      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        <div className="h-48 animate-pulse rounded-3xl bg-slate-200 motion-reduce:animate-none" />
        <div className="h-48 animate-pulse rounded-3xl bg-slate-200 motion-reduce:animate-none" />
      </div>
    </section>
  );
}

function DailyError({ onRetry }: { onRetry: () => void }) {
  return (
    <section
      aria-labelledby="daily-error-title"
      className="form-card border-rose-200 bg-rose-50"
    >
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-rose-700">
        Home
      </p>
      <h1
        id="daily-error-title"
        className="mt-3 text-3xl font-semibold text-rose-950"
      >
        RevenueOS couldn’t load your day.
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-rose-900">
        Try again, or continue directly to your current customer work.
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <button type="button" className="primary-button" onClick={onRetry}>
          Retry
        </button>
        <Link className="secondary-button" href="/interactions">
          Open interactions
        </Link>
        <Link className="secondary-button" href="/opportunities">
          Open opportunities
        </Link>
      </div>
    </section>
  );
}

function NewUserWelcome() {
  return (
    <article className="relative overflow-hidden rounded-[2rem] bg-slate-950 p-7 text-white shadow-xl sm:p-10">
      <div className="absolute -right-20 -top-24 size-64 rounded-full bg-teal-400/20 blur-3xl" />
      <div className="relative max-w-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-300">
          Welcome to RevenueOS
        </p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight">
          Let’s get your first deal into RevenueOS.
        </h2>
        <p className="mt-4 text-sm leading-7 text-slate-300">
          Add an opportunity, then create your next customer interaction.
          RevenueOS will help you prepare, capture what changed and follow
          through.
        </p>
        <Link className="primary-button mt-6" href="/opportunities/new">
          Add an opportunity
        </Link>
      </div>
    </article>
  );
}

function CaughtUp() {
  return (
    <article className="rounded-[2rem] border border-emerald-200 bg-emerald-50 p-7 sm:p-8">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-800">
        Focus now
      </p>
      <h2 className="mt-3 text-2xl font-semibold text-emerald-950">
        You’re caught up.
      </h2>
      <p className="mt-2 text-sm leading-6 text-emerald-900">
        No evidence-backed work needs urgent attention right now. You can still
        review your pipeline or prepare upcoming interactions.
      </p>
    </article>
  );
}

function PriorityCard({
  priority,
  timezone,
}: {
  priority: DailyPriority;
  timezone: string;
}) {
  return (
    <article className="relative overflow-hidden rounded-[2rem] bg-slate-950 p-6 text-white shadow-xl sm:p-8">
      <div className="absolute -right-12 -top-16 size-52 rounded-full bg-teal-400/20 blur-3xl" />
      <div className="relative flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-300">
            Top priority
          </p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
            {priority.title}
          </h2>
          <p className="mt-2 text-sm font-semibold text-slate-200">
            {priority.startsAt
              ? `${formatTime(priority.startsAt, timezone)} · `
              : ""}
            {priority.context}
          </p>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            {priority.reason}
          </p>
        </div>
        <Link className="primary-button shrink-0" href={priority.href}>
          {priority.ctaLabel} <span aria-hidden="true">→</span>
        </Link>
      </div>
    </article>
  );
}

function MobileNextInteraction({
  interaction,
  timezone,
}: {
  interaction: DailyInteraction;
  timezone: string;
}) {
  return (
    <article className="rounded-3xl bg-slate-950 p-5 text-white shadow-lg">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-300">
        Next
      </p>
      <h2 className="mt-2 text-xl font-semibold">
        {interaction.companyName ?? interaction.title}
      </h2>
      <p className="mt-1 text-sm text-slate-300">
        {formatTime(interaction.startsAt, timezone)} · {interaction.title}
      </p>
      <p className="mt-2 text-sm text-slate-400">{interaction.context}</p>
      <Link className="primary-button mt-4 w-full" href={interaction.href}>
        {interaction.ctaLabel}
      </Link>
    </article>
  );
}

function InteractionsSection({
  interactions,
  total,
  available,
  timezone,
}: {
  interactions: DailyInteraction[];
  total: number;
  available: boolean;
  timezone: string;
}) {
  return (
    <SectionCard
      eyebrow="What is happening today?"
      title="Today’s interactions"
      count={total}
    >
      {!available ? (
        <Unavailable label="Interactions" />
      ) : interactions.length === 0 ? (
        <EmptyLine>No customer interactions scheduled today.</EmptyLine>
      ) : (
        <ul className="divide-y divide-slate-100">
          {interactions.map((interaction) => (
            <li
              key={interaction.id}
              className="flex flex-col gap-4 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-wide text-teal-700">
                  {formatTime(interaction.startsAt, timezone)} ·{" "}
                  {humanise(interaction.interactionType)}
                </p>
                <h3 className="mt-1 font-semibold text-slate-950">
                  {interaction.title}
                </h3>
                <p className="mt-1 text-sm text-slate-600">
                  {interaction.context}
                </p>
              </div>
              <Link
                className="secondary-button shrink-0"
                href={interaction.href}
              >
                {interaction.ctaLabel}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function ActionsSection({
  actions,
  count,
  overdueCount,
  available,
  timezone,
}: {
  actions: DailyAction[];
  count: number;
  overdueCount: number;
  available: boolean;
  timezone: string;
}) {
  return (
    <SectionCard
      eyebrow="What needs my attention?"
      title="Actions"
      count={count}
    >
      {!available ? (
        <Unavailable label="Actions" />
      ) : actions.length === 0 ? (
        <EmptyLine>No current Actions need your attention.</EmptyLine>
      ) : (
        <>
          {overdueCount > 0 ? (
            <p className="mb-4 text-sm font-semibold text-rose-800">
              {overdueCount} overdue
            </p>
          ) : null}
          <ul className="grid gap-3">
            {actions.map((action) => (
              <li
                key={action.id}
                className="rounded-2xl border border-slate-200 p-4"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                      {action.timing === "overdue"
                        ? "Overdue"
                        : action.timing === "due_today"
                          ? "Due today"
                          : action.dueAt
                            ? `Due ${formatShortDate(action.dueAt, timezone)}`
                            : action.stateLabel}
                    </p>
                    <h3 className="mt-1 font-semibold text-slate-950">
                      {action.title}
                    </h3>
                    <p className="mt-1 text-sm text-slate-600">
                      {action.opportunityName} · {action.stateLabel}
                    </p>
                  </div>
                  <Link
                    className="secondary-button shrink-0"
                    href={action.href}
                  >
                    {action.ctaLabel}
                  </Link>
                </div>
              </li>
            ))}
          </ul>
          <Link
            className="mt-4 inline-flex min-h-11 items-center text-sm font-bold text-teal-800"
            href="/opportunities"
          >
            View all opportunity Actions{" "}
            <span aria-hidden="true" className="ml-1">
              →
            </span>
          </Link>
        </>
      )}
    </SectionCard>
  );
}

function DealsSection({
  deals,
  count,
  available,
}: {
  deals: DailyDealAttention[];
  count: number;
  available: boolean;
}) {
  return (
    <SectionCard
      eyebrow="Which deals need help?"
      title="Deals needing attention"
      count={count}
    >
      {!available ? (
        <Unavailable label="Deal attention" />
      ) : deals.length === 0 ? (
        <EmptyLine>
          No evidence-backed deals need attention right now.
        </EmptyLine>
      ) : (
        <ul className="grid gap-3">
          {deals.map((deal) => (
            <li
              key={deal.opportunityId}
              className="rounded-2xl border border-slate-200 p-4"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-amber-800">
                    {deal.priority === "urgent"
                      ? "Urgent"
                      : deal.priority === "needs_attention"
                        ? "Needs attention"
                        : "Watch"}
                  </p>
                  <h3 className="mt-1 font-semibold text-slate-950">
                    {deal.opportunityName}
                    {deal.estimatedValue && deal.currency
                      ? ` · ${formatMoney(deal.estimatedValue, deal.currency)}`
                      : ""}
                  </h3>
                  {deal.companyName ? (
                    <p className="mt-1 text-sm text-slate-600">
                      {deal.companyName}
                    </p>
                  ) : null}
                  <ul className="mt-3 space-y-1 text-sm text-slate-700">
                    {deal.reasons.map((reason) => (
                      <li key={reason.code}>• {reason.text}</li>
                    ))}
                  </ul>
                </div>
                <Link className="secondary-button shrink-0" href={deal.href}>
                  Review opportunity
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function MobileDaySummary({
  interactions,
  total,
  available,
  timezone,
  primaryInteractionId,
}: {
  interactions: DailyInteraction[];
  total: number;
  available: boolean;
  timezone: string;
  primaryInteractionId: string | null;
}) {
  const remaining = interactions.filter(
    (interaction) => interaction.id !== primaryInteractionId,
  );
  return (
    <SectionCard
      eyebrow="Day overview"
      title="Today’s interactions"
      count={total}
    >
      {!available ? (
        <Unavailable label="Interactions" />
      ) : remaining.length === 0 ? (
        <EmptyLine>
          {total === 0
            ? "No customer interactions scheduled today."
            : "No more customer interactions today."}
        </EmptyLine>
      ) : (
        <ul className="space-y-3">
          {remaining.slice(0, 2).map((item) => (
            <li key={item.id} className="text-sm text-slate-700">
              <Link
                className="block min-h-11 rounded-xl p-2 font-semibold hover:bg-slate-50"
                href={item.href}
              >
                {formatTime(item.startsAt, timezone)} · {item.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Link
        className="mt-3 inline-flex min-h-11 items-center text-sm font-bold text-teal-800"
        href="/interactions"
      >
        View day →
      </Link>
    </SectionCard>
  );
}

function PipelineCard({
  pipeline,
  available,
}: {
  pipeline: DailyPipelineSummary;
  available: boolean;
}) {
  return (
    <SectionCard
      eyebrow="Am I on track?"
      title="Open pipeline"
      count={pipeline.openOpportunityCount}
    >
      {!available ? (
        <Unavailable label="Pipeline" />
      ) : pipeline.state === "empty" ? (
        <EmptyLine>{pipeline.safeMessage}</EmptyLine>
      ) : pipeline.state === "single_currency" && pipeline.currencies[0] ? (
        <div>
          <p className="text-3xl font-semibold tracking-tight text-slate-950">
            {formatMoney(
              pipeline.currencies[0].openValue,
              pipeline.currencies[0].currency,
            )}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            {formatMoney(
              pipeline.currencies[0].closingThisMonthValue,
              pipeline.currencies[0].currency,
            )}{" "}
            closing this month
          </p>
        </div>
      ) : (
        <div>
          <p className="text-lg font-semibold text-slate-950">
            {pipeline.currencyCount} currencies
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {pipeline.safeMessage}
          </p>
          <dl className="mt-4 hidden space-y-3 border-t border-slate-100 pt-4 lg:block">
            {pipeline.currencies.slice(0, 3).map((item) => (
              <div
                key={item.currency}
                className="flex items-center justify-between gap-4 text-sm"
              >
                <dt className="font-semibold text-slate-600">
                  {item.currency}
                </dt>
                <dd className="font-semibold text-slate-950">
                  {formatMoney(item.openValue, item.currency)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      <Link
        className="mt-4 inline-flex min-h-11 items-center text-sm font-bold text-teal-800"
        href="/opportunities"
      >
        Review pipeline →
      </Link>
      <p className="mt-3 text-xs leading-5 text-slate-500">
        Descriptive pipeline only. No forecast or target is inferred.
      </p>
    </SectionCard>
  );
}

function RecommendationsCard({
  recommendations,
  available,
}: {
  recommendations: DailyRecommendation[];
  available: boolean;
}) {
  return (
    <SectionCard
      eyebrow="What should I do next?"
      title="Recommended focus"
      count={recommendations.length}
    >
      {!available ? (
        <Unavailable label="Recommended focus" />
      ) : recommendations.length === 0 ? (
        <EmptyLine>No current Next Best Action is ready.</EmptyLine>
      ) : (
        <ul className="space-y-4">
          {recommendations.map((item) => (
            <li key={item.sourceId}>
              <p className="text-sm font-semibold leading-6 text-slate-950">
                {item.recommendation}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {item.opportunityName}
              </p>
              <Link
                className="mt-2 inline-flex min-h-11 items-center text-sm font-bold text-teal-800"
                href={item.href}
              >
                {item.ctaLabel} →
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function SectionCard({
  eyebrow,
  title,
  count,
  children,
}: {
  eyebrow: string;
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700">
            {eyebrow}
          </p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">
            {title}
          </h2>
        </div>
        <span
          aria-label={`${count} items`}
          className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-100 text-sm font-bold text-slate-700"
        >
          {count}
        </span>
      </div>
      {children}
    </section>
  );
}

function Unavailable({ label }: { label: string }) {
  return (
    <p role="status" className="text-sm text-slate-600">
      {label} temporarily unavailable.
    </p>
  );
}

function EmptyLine({ children }: { children: React.ReactNode }) {
  return <p className="text-sm leading-6 text-slate-600">{children}</p>;
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function formatLocalDate(value: string) {
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "full" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function formatTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-AU", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: timezone,
  }).format(new Date(value));
}

function formatShortDate(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    timeZone: timezone,
  }).format(new Date(value));
}

function formatUpdated(value: string) {
  const seconds = Math.max(
    0,
    Math.round((Date.now() - new Date(value).getTime()) / 1_000),
  );
  if (seconds < 60) return "just now";
  return `${Math.floor(seconds / 60)} min ago`;
}

function formatMoney(value: string, currency: string) {
  const [wholeRaw, fractionRaw = "00"] = value.split(".");
  const negative = wholeRaw.startsWith("-");
  const digits = negative ? wholeRaw.slice(1) : wholeRaw;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/gu, ",");
  return `${currency} ${negative ? "-" : ""}${grouped}.${fractionRaw.padEnd(2, "0").slice(0, 2)}`;
}
