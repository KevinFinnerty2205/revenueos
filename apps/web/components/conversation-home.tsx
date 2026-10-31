"use client";

import type {
  DailyAction,
  DailyInteraction,
  DailyResponse,
  EntityPage,
  Interaction,
} from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatInteractionDate } from "@/lib/interactions";

function conversationHref(href: string): string {
  return href
    .replace(/^\/interactions\//u, "/conversations/")
    .replace(/\/companion(?=$|#)/u, "/workspace");
}

export function ConversationHome() {
  const [daily, setDaily] = useState<DailyResponse | null>(null);
  const [recent, setRecent] = useState<Interaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyWarning, setHistoryWarning] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    Promise.allSettled([
      apiRequest<DailyResponse>(
        `/api/v1/daily?${new URLSearchParams({ timezone }).toString()}`,
        { signal: controller.signal },
      ),
      apiRequest<EntityPage<Interaction>>(
        "/api/v1/interactions?page=1&pageSize=6&status=completed&sortBy=start_at&sortOrder=desc",
        { signal: controller.signal },
      ),
    ])
      .then(([dayResult, historyResult]) => {
        if (dayResult.status === "rejected") throw dayResult.reason;
        setDaily(dayResult.value);
        setError(null);
        if (historyResult.status === "fulfilled") {
          setRecent(historyResult.value.items);
          setHistoryWarning(null);
        } else {
          setHistoryWarning(
            "Recent conversation history is temporarily unavailable. Your next conversation is still shown.",
          );
        }
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Your conversation workspace could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [retryKey]);

  if (loading && !daily) return <HomeLoading />;
  if (!daily) {
    return (
      <section className="form-card border-rose-200 bg-rose-50" role="alert">
        <h1 className="text-3xl font-semibold text-rose-950">
          Oryntela couldn’t load your conversations.
        </h1>
        <p className="mt-3 text-sm text-rose-900">{error}</p>
        <button
          type="button"
          className="primary-button mt-5"
          onClick={() => {
            setLoading(true);
            setRetryKey((value) => value + 1);
          }}
        >
          Try again
        </button>
      </section>
    );
  }

  const firstName = daily.userDisplayName.split(/\s/u)[0] || "there";
  const upcoming = daily.todayInteractions.filter(
    (item) => item.id !== daily.nextInteraction?.id,
  );

  return (
    <section aria-labelledby="conversation-home-title">
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
            {formatLocalDate(daily.localDate)}
          </p>
          <h1
            id="conversation-home-title"
            className="mt-3 text-4xl font-semibold tracking-[-0.035em] text-slate-950 sm:text-5xl"
          >
            {greeting()}, {firstName}
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            Prepare for what is next, stay present in the conversation, and keep
            every commitment easy to find.
          </p>
        </div>
        <Link className="secondary-button" href="/assistant?mode=ask">
          Ask Oryntela
        </Link>
      </header>
      {historyWarning ? (
        <p
          role="status"
          className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          {historyWarning}
        </p>
      ) : null}

      {error ? (
        <p
          role="status"
          className="mb-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-950"
        >
          Your last loaded view is shown. Refresh the page to try again.
        </p>
      ) : null}

      {daily.nextInteraction ? (
        <NextConversation
          interaction={daily.nextInteraction}
          timezone={daily.timezone}
        />
      ) : (
        <EmptyNextConversation />
      )}

      <div className="mt-7 grid gap-6 xl:grid-cols-2">
        <HomeSection
          eyebrow="Coming up"
          title="Upcoming conversations"
          action={{ href: "/conversations", label: "View all" }}
        >
          {upcoming.length ? (
            <ul className="divide-y divide-slate-100">
              {upcoming.slice(0, 4).map((item) => (
                <UpcomingRow
                  key={item.id}
                  item={item}
                  timezone={daily.timezone}
                />
              ))}
            </ul>
          ) : (
            <EmptyLine>No other conversations are scheduled today.</EmptyLine>
          )}
        </HomeSection>

        <HomeSection
          eyebrow="Keep moving"
          title="Follow-ups needing attention"
          action={{ href: "/conversations", label: "Conversation history" }}
        >
          {daily.actions.items.length ? (
            <ul className="divide-y divide-slate-100">
              {daily.actions.items.slice(0, 4).map((action) => (
                <FollowUpRow key={action.id} action={action} />
              ))}
            </ul>
          ) : (
            <EmptyLine>No follow-ups need attention right now.</EmptyLine>
          )}
        </HomeSection>

        <div className="xl:col-span-2">
          <HomeSection
            eyebrow="Memory"
            title="Recent conversations"
            action={{ href: "/assistant", label: "Search or ask" }}
          >
            {recent.length ? (
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {recent.slice(0, 6).map((item) => (
                  <li key={item.id}>
                    <Link
                      href={`/conversations/${item.id}`}
                      className="block h-full rounded-2xl border border-slate-200 p-4 transition hover:border-brand-secondary/40 hover:bg-brand-secondary/5 focus:outline-none focus:ring-2 focus:ring-brand-focus"
                    >
                      <p className="text-xs font-bold uppercase tracking-wide text-brand-secondary">
                        {humanise(item.interactionType)}
                      </p>
                      <h3 className="mt-2 font-semibold text-slate-950">
                        {item.title}
                      </h3>
                      <p className="mt-2 text-sm text-slate-500">
                        {formatInteractionDate(
                          item.actualEndAt ?? item.scheduledStartAt,
                        )}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyLine>
                Completed conversations will become your searchable relationship
                history.
              </EmptyLine>
            )}
          </HomeSection>
        </div>
      </div>
    </section>
  );
}

function NextConversation({
  interaction,
  timezone,
}: {
  interaction: DailyInteraction;
  timezone: string;
}) {
  return (
    <article className="relative overflow-hidden rounded-[1.75rem] bg-brand-primary p-7 text-white shadow-[0_22px_60px_rgba(7,24,38,0.12)] sm:p-9">
      <div className="absolute -right-20 -top-24 size-72 rounded-full bg-brand-secondary/15 blur-3xl" />
      <div className="relative flex flex-col gap-7 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-highlight">
            Next conversation · {formatTime(interaction.startsAt, timezone)}
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            {interaction.title}
          </h2>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            {interaction.context}
          </p>
          <p className="mt-4 text-sm font-semibold text-brand-highlight">
            {preparationMessage(interaction.preparationState)}
          </p>
        </div>
        <Link
          className="inline-flex min-h-12 shrink-0 items-center justify-center rounded-xl bg-white px-5 text-sm font-bold text-brand-primary transition hover:bg-brand-secondary/10 focus:outline-none focus:ring-2 focus:ring-brand-highlight focus:ring-offset-2 focus:ring-offset-brand-primary"
          href={conversationHref(interaction.href)}
        >
          {interaction.preparationState === "not_prepared"
            ? "Prepare now"
            : interaction.ctaLabel}
        </Link>
      </div>
    </article>
  );
}

function EmptyNextConversation() {
  return (
    <article className="rounded-[1.75rem] border border-slate-200 bg-white p-7 sm:p-9">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
        Next conversation
      </p>
      <h2 className="mt-3 text-2xl font-semibold text-slate-950">
        Nothing is scheduled yet.
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
        Add a meeting, outbound call, general conversation or event note. A
        company and opportunity are optional.
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link className="primary-button" href="/conversations/new">
          Add conversation
        </Link>
        <Link className="secondary-button" href="/knowledge">
          Set up company knowledge
        </Link>
      </div>
    </article>
  );
}

function HomeSection({
  eyebrow,
  title,
  action,
  children,
}: {
  eyebrow: string;
  title: string;
  action: { href: string; label: string };
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 sm:p-7">
      <header className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
            {eyebrow}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">{title}</h2>
        </div>
        <Link
          className="text-sm font-bold text-brand-primary hover:underline"
          href={action.href}
        >
          {action.label}
        </Link>
      </header>
      {children}
    </section>
  );
}

function UpcomingRow({
  item,
  timezone,
}: {
  item: DailyInteraction;
  timezone: string;
}) {
  return (
    <li>
      <Link
        className="flex min-h-20 items-center justify-between gap-4 py-4 first:pt-0 last:pb-0 focus:outline-none focus:ring-2 focus:ring-brand-focus"
        href={conversationHref(item.href)}
      >
        <span>
          <span className="block text-xs font-bold uppercase tracking-wide text-slate-500">
            {formatTime(item.startsAt, timezone)} ·{" "}
            {humanise(item.interactionType)}
          </span>
          <span className="mt-1 block font-semibold text-slate-950">
            {item.title}
          </span>
        </span>
        <span className="text-sm font-bold text-brand-primary">Open</span>
      </Link>
    </li>
  );
}

function FollowUpRow({ action }: { action: DailyAction }) {
  return (
    <li className="flex min-h-20 items-center justify-between gap-4 py-4 first:pt-0 last:pb-0">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
          {action.timing === "overdue" ? "Overdue" : humanise(action.timing)}
        </p>
        <p className="mt-1 font-semibold text-slate-950">{action.title}</p>
        <p className="mt-1 text-sm text-slate-500">{action.companyName}</p>
      </div>
      <Link
        className="text-sm font-bold text-brand-primary hover:underline"
        href={
          action.href.startsWith("/opportunities/")
            ? "/conversations"
            : conversationHref(action.href)
        }
      >
        Review
      </Link>
    </li>
  );
}

function EmptyLine({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
      {children}
    </p>
  );
}

function HomeLoading() {
  return (
    <section aria-busy="true" aria-label="Loading conversation home">
      <div className="h-24 animate-pulse rounded-2xl bg-slate-200 motion-reduce:animate-none" />
      <div className="mt-7 h-64 animate-pulse rounded-[1.75rem] bg-slate-200 motion-reduce:animate-none" />
      <div className="mt-7 grid gap-6 sm:grid-cols-2">
        <div className="h-52 animate-pulse rounded-3xl bg-slate-200 motion-reduce:animate-none" />
        <div className="h-52 animate-pulse rounded-3xl bg-slate-200 motion-reduce:animate-none" />
      </div>
    </section>
  );
}

function preparationMessage(
  state: DailyInteraction["preparationState"],
): string {
  if (state === "prepared") return "Preparation brief ready";
  if (state === "active") return "Conversation in progress";
  if (state === "capture_needed") return "Notes and follow-up need review";
  if (state === "complete") return "Conversation captured";
  return "Preparation has not been generated yet";
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function formatLocalDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(`${value}T12:00:00`));
}

function formatTime(value: string, timezone: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: timezone,
  }).format(new Date(value));
}
