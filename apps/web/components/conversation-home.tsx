"use client";

import type {
  Company,
  DailyAction,
  DailyInteraction,
  DailyResponse,
  Interaction,
} from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AccountAvatar } from "@/components/account-avatar";
import { useVerifiedOrganisation } from "@/components/verified-organisation-context";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatInteractionDate } from "@/lib/interactions";
import {
  decodeTenantPage,
  isCompanyResponse,
  isInteractionResponse,
} from "@/lib/private-response-identity";

function conversationHref(href: string): string {
  return href
    .replace(/^\/interactions\//u, "/conversations/")
    .replace(/\/companion(?=$|#)/u, "/workspace");
}

type SourceState = "loading" | "available" | "unavailable";

export function ConversationHome() {
  const organisation = useVerifiedOrganisation();
  if (organisation.status === "loading") return <HomeLoading />;
  if (organisation.status !== "available") {
    return (
      <section className="form-card border-rose-200 bg-rose-50" role="alert">
        <h1 className="text-3xl font-semibold text-rose-950">
          Oryntela couldn’t verify your organisation.
        </h1>
        <p className="mt-3 text-sm text-rose-900">
          Your private conversation workspace is temporarily unavailable.
        </p>
      </section>
    );
  }
  return (
    <ConversationHomeSession
      key={organisation.organisationId}
      organisationId={organisation.organisationId}
    />
  );
}

function ConversationHomeSession({
  organisationId,
}: {
  organisationId: string;
}) {
  const [daily, setDaily] = useState<DailyResponse | null>(null);
  const [recent, setRecent] = useState<Interaction[]>([]);
  const [accounts, setAccounts] = useState<Company[]>([]);
  const [dailyState, setDailyState] = useState<SourceState>("loading");
  const [historyState, setHistoryState] = useState<SourceState>("loading");
  const [accountState, setAccountState] = useState<SourceState>("loading");
  const [retrying, setRetrying] = useState(false);
  const [dailyRetryKey, setDailyRetryKey] = useState(0);
  const [secondaryRetryKey, setSecondaryRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    const dailyRequest = apiRequest<DailyResponse>(
      `/api/v1/daily?${new URLSearchParams({ timezone }).toString()}`,
      { signal: controller.signal },
    ).then(
      (value) => {
        if (controller.signal.aborted) return;
        setDaily(value);
        setDailyState("available");
        setRetrying(false);
      },
      () => {
        if (controller.signal.aborted) return;
        setDaily(null);
        setDailyState("unavailable");
        setRetrying(false);
      },
    );
    void dailyRequest;
    return () => controller.abort();
  }, [dailyRetryKey]);

  useEffect(() => {
    const controller = new AbortController();
    const historyRequest = apiRequest<unknown>(
      "/api/v1/interactions?page=1&pageSize=6&status=completed&sortBy=start_at&sortOrder=desc",
      { signal: controller.signal },
    ).then(
      (value) => {
        if (controller.signal.aborted) return;
        const page = decodeTenantPage(
          value,
          organisationId,
          isInteractionResponse,
          { expectedPage: 1 },
        );
        if (page === null) {
          setHistoryState("unavailable");
          return;
        }
        setRecent(page.items);
        setHistoryState("available");
      },
      () => {
        if (controller.signal.aborted) return;
        setHistoryState("unavailable");
      },
    );
    const accountRequest = apiRequest<unknown>(
      "/api/v1/companies?page=1&pageSize=8&sortBy=name&sortOrder=asc",
      { signal: controller.signal },
    ).then(
      (value) => {
        if (controller.signal.aborted) return;
        const page = decodeTenantPage(
          value,
          organisationId,
          isCompanyResponse,
          { expectedPage: 1 },
        );
        if (page === null) {
          setAccountState("unavailable");
          return;
        }
        setAccounts(page.items);
        setAccountState("available");
      },
      () => {
        if (controller.signal.aborted) return;
        setAccountState("unavailable");
      },
    );

    void historyRequest;
    void accountRequest;
    return () => controller.abort();
  }, [organisationId, secondaryRetryKey]);

  const usefulSecondarySource =
    historyState === "available" ||
    accountState === "available" ||
    recent.length > 0 ||
    accounts.length > 0;

  if (dailyState === "loading") {
    return <HomeLoading />;
  }
  if (!daily) {
    if (usefulSecondarySource) {
      return (
        <ReducedConversationHome
          accounts={accounts}
          accountState={accountState}
          historyState={historyState}
          recent={recent}
          retrying={retrying}
          retry={() => {
            setRetrying(true);
            setDailyRetryKey((value) => value + 1);
          }}
        />
      );
    }

    if (historyState === "loading" || accountState === "loading") {
      return <HomeLoading />;
    }

    return (
      <section className="form-card border-rose-200 bg-rose-50" role="alert">
        <h1 className="text-3xl font-semibold text-rose-950">
          Oryntela couldn’t load your conversations.
        </h1>
        <p className="mt-3 text-sm text-rose-900">
          Your conversation workspace is temporarily unavailable. Please try
          again.
        </p>
        <button
          type="button"
          className="primary-button mt-5"
          disabled={retrying}
          onClick={() => {
            setRetrying(true);
            setDailyRetryKey((value) => value + 1);
            setSecondaryRetryKey((value) => value + 1);
          }}
        >
          {retrying ? "Trying again…" : "Try again"}
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
      {historyState === "unavailable" ? (
        <p
          role="status"
          className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          Recent conversation history is temporarily unavailable. Your next
          conversation is still shown.
        </p>
      ) : null}
      {accountState === "unavailable" ? (
        <p
          role="status"
          className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          Account conversation links are temporarily unavailable. The rest of
          your conversation workspace is still shown.
        </p>
      ) : null}
      {historyState === "loading" ? (
        <p
          role="status"
          className="mb-6 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600"
        >
          Recent conversation history is still loading.
        </p>
      ) : null}
      {accountState === "loading" ? (
        <p
          role="status"
          className="mb-6 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600"
        >
          Account conversation links are still loading.
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

      {accounts.length ? <AccountDirectory accounts={accounts} /> : null}

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
          {!daily.availability.privateFollowUps ? (
            <p
              className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-950"
              role="status"
            >
              Private follow-up drafts are temporarily unavailable. Shared
              follow-ups are still shown when available.
            </p>
          ) : null}
          {daily.privateFollowUps.items.length || daily.actions.items.length ? (
            <ul
              className={`${daily.availability.privateFollowUps ? "" : "mt-3 "}divide-y divide-slate-100`}
              aria-label="Follow-ups needing attention"
            >
              {daily.privateFollowUps.items.map((followUp) => (
                <PrivateFollowUpRow
                  key={followUp.interactionId}
                  followUp={followUp}
                />
              ))}
              {daily.actions.items.slice(0, 4).map((action) => (
                <FollowUpRow key={action.id} action={action} />
              ))}
            </ul>
          ) : daily.availability.privateFollowUps ? (
            <EmptyLine>No follow-ups need attention right now.</EmptyLine>
          ) : null}
        </HomeSection>

        {historyState === "available" || recent.length > 0 ? (
          <div className="xl:col-span-2">
            <HomeSection
              eyebrow="Memory"
              title="Recent conversations"
              action={{ href: "/assistant", label: "Search or ask" }}
            >
              <RecentConversationGrid recent={recent} />
            </HomeSection>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function ReducedConversationHome({
  accounts,
  accountState,
  historyState,
  recent,
  retry,
  retrying,
}: {
  accounts: Company[];
  accountState: SourceState;
  historyState: SourceState;
  recent: Interaction[];
  retry: () => void;
  retrying: boolean;
}) {
  const optionalSourceLoading =
    accountState === "loading" || historyState === "loading";

  return (
    <section
      aria-labelledby="conversation-home-title"
      aria-busy={retrying || optionalSourceLoading}
    >
      <header className="mb-7 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
            Relationship memory
          </p>
          <h1
            id="conversation-home-title"
            className="mt-3 text-4xl font-semibold tracking-[-0.035em] text-slate-950 sm:text-5xl"
          >
            Conversation workspace
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            Keep working from the conversation history and account memory that
            are available now.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link className="primary-button" href="/conversations/new">
            Add conversation
          </Link>
          <Link className="secondary-button" href="/assistant">
            Search or ask
          </Link>
        </div>
      </header>

      <div
        className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-950"
        role="status"
      >
        <p>
          Today&apos;s schedule and follow-ups are temporarily unavailable. No
          schedule or follow-up status is shown until that source recovers.
        </p>
        <button
          type="button"
          className="secondary-button mt-4"
          disabled={retrying}
          onClick={retry}
        >
          {retrying ? "Trying again…" : "Try Daily again"}
        </button>
      </div>

      {historyState === "unavailable" ? (
        <p
          role="status"
          className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          Recent conversation history is temporarily unavailable.
        </p>
      ) : null}
      {accountState === "unavailable" ? (
        <p
          role="status"
          className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          Account conversation links are temporarily unavailable.
        </p>
      ) : null}
      {historyState === "loading" ? (
        <p
          role="status"
          className="mt-5 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600"
        >
          Recent conversation history is still loading.
        </p>
      ) : null}
      {accountState === "loading" ? (
        <p
          role="status"
          className="mt-5 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600"
        >
          Account conversation links are still loading.
        </p>
      ) : null}

      {accountState === "available" || accounts.length > 0 ? (
        accounts.length ? (
          <AccountDirectory accounts={accounts} />
        ) : (
          <div className="mt-7">
            <HomeSection
              eyebrow="Relationship memory"
              title="Accounts"
              action={{ href: "/conversations", label: "View all" }}
            >
              <EmptyLine>
                Accounts will appear here when a conversation is linked to one.
              </EmptyLine>
            </HomeSection>
          </div>
        )
      ) : null}

      {historyState === "available" || recent.length > 0 ? (
        <div className="mt-7">
          <HomeSection
            eyebrow="Memory"
            title="Recent conversations"
            action={{ href: "/assistant", label: "Search or ask" }}
          >
            <RecentConversationGrid recent={recent} />
          </HomeSection>
        </div>
      ) : null}
    </section>
  );
}

function RecentConversationGrid({ recent }: { recent: Interaction[] }) {
  if (!recent.length) {
    return (
      <EmptyLine>
        Completed conversations will become your searchable relationship
        history.
      </EmptyLine>
    );
  }

  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {recent.slice(0, 6).map((item) => (
        <li key={item.id}>
          <Link
            href={`/conversations/${encodeURIComponent(item.id)}`}
            className="block h-full rounded-2xl border border-slate-200 p-4 transition hover:border-brand-secondary/40 hover:bg-brand-secondary/5 focus:outline-none focus:ring-2 focus:ring-brand-focus"
          >
            <p className="text-xs font-bold uppercase tracking-wide text-brand-secondary">
              {humanise(item.interactionType)}
            </p>
            <h3 className="mt-2 font-semibold text-slate-950">{item.title}</h3>
            <p className="mt-2 text-sm text-slate-500">
              {formatInteractionDate(item.actualEndAt ?? item.scheduledStartAt)}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function AccountDirectory({ accounts }: { accounts: Company[] }) {
  return (
    <section
      className="mt-7 rounded-3xl border border-brand-primary/10 bg-white p-6 sm:p-7"
      aria-labelledby="home-accounts-title"
    >
      <header className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
            Relationship memory
          </p>
          <h2
            id="home-accounts-title"
            className="mt-2 text-xl font-semibold text-slate-950"
          >
            Accounts
          </h2>
        </div>
        <Link
          className="text-sm font-bold text-brand-primary hover:underline"
          href="/conversations"
        >
          View all
        </Link>
      </header>
      <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {accounts.map((account) => (
          <li key={account.id}>
            <Link
              className="flex min-h-16 items-center gap-3 rounded-2xl border border-brand-primary/10 px-3 py-2 transition hover:border-brand-secondary/40 hover:bg-brand-secondary/5 focus:outline-none focus:ring-2 focus:ring-brand-focus"
              href={`/conversations/accounts/${encodeURIComponent(account.id)}#conversations`}
            >
              <AccountAvatar
                accountId={account.id}
                name={account.name}
                size="compact"
                website={account.website}
              />
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-brand-primary">
                  {account.name}
                </span>
                <span className="mt-0.5 block text-xs text-brand-muted">
                  Open conversation memory
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
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
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-primary-foreground/80">
            Next conversation · {formatTime(interaction.startsAt, timezone)}
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            {interaction.title}
          </h2>
          {interaction.companyName || interaction.participantNames.length ? (
            <p className="mt-3 text-sm font-semibold text-white">
              {[interaction.companyName, ...interaction.participantNames]
                .filter(Boolean)
                .join(" · ")}
            </p>
          ) : null}
          <p className="mt-3 text-sm leading-6 text-slate-300">
            {interaction.context}
          </p>
          <p className="mt-4 text-sm font-semibold text-brand-primary-foreground">
            {preparationMessage(interaction.preparationState)}
          </p>
        </div>
        <Link
          className="inline-flex min-h-12 shrink-0 items-center justify-center rounded-xl bg-white px-5 text-sm font-bold text-brand-primary transition hover:bg-brand-secondary/10 focus:outline-none focus:ring-2 focus:ring-brand-accent focus:ring-offset-2 focus:ring-offset-brand-primary"
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
          {item.companyName || item.participantNames.length ? (
            <span className="mt-1 block text-sm text-slate-500">
              {[item.companyName, ...item.participantNames]
                .filter(Boolean)
                .join(" · ")}
            </span>
          ) : null}
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

function PrivateFollowUpRow({
  followUp,
}: {
  followUp: DailyResponse["privateFollowUps"]["items"][number];
}) {
  return (
    <li className="flex min-h-20 items-center justify-between gap-4 py-4 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
          Private draft · {formatInteractionDate(followUp.updatedAt)}
        </p>
        <p className="mt-1 break-words font-semibold text-slate-950">
          {followUp.interactionTitle}
        </p>
        {followUp.companyName ? (
          <p className="mt-1 text-sm text-slate-500">{followUp.companyName}</p>
        ) : null}
      </div>
      <Link
        className="shrink-0 text-sm font-bold text-brand-primary hover:underline focus:outline-none focus:ring-2 focus:ring-brand-focus"
        href={followUp.href}
      >
        {followUp.ctaLabel} private draft
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
