"use client";

import type {
  Company,
  Contact,
  EntityPage,
  Interaction,
  InteractionLifecycleStatus,
  InteractionType,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { AccountAvatar } from "@/components/account-avatar";
import { InteractionCard } from "@/components/interaction-card";
import { ProviderCalendarContext } from "@/components/microsoft-calendar-context";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import {
  formatInteractionDate,
  interactionStatuses,
  interactionTypes,
} from "@/lib/interactions";

type AccountSummary = Pick<
  Company,
  "id" | "name" | "website" | "industry" | "location"
>;

export function InteractionList() {
  const [result, setResult] = useState<EntityPage<Interaction> | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState(0);
  const [retryKey, setRetryKey] = useState(0);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [interactionType, setInteractionType] = useState<InteractionType | "">(
    "",
  );
  const [interactionStatus, setInteractionStatus] = useState<
    InteractionLifecycleStatus | ""
  >("");

  useEffect(() => {
    const controller = new AbortController();
    const parameters = interactionParameters(
      search,
      interactionType,
      interactionStatus,
    );
    Promise.all([
      apiRequest<EntityPage<Interaction>>(
        "/api/v1/interactions?" + parameters.toString(),
        { signal: controller.signal },
      ),
      apiRequest<EntityPage<Company>>("/api/v1/companies?pageSize=100", {
        signal: controller.signal,
      }),
      apiRequest<EntityPage<Contact>>("/api/v1/contacts?pageSize=100", {
        signal: controller.signal,
      }),
    ])
      .then(async ([interactions, companyPage, contactPage]) => {
        const context = await hydrateLinkedContext(
          interactions.items,
          companyPage.items,
          contactPage.items,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setResult(interactions);
        setCompanies(context.companies);
        setContacts(context.contacts);
        setLoadedAt(Date.now());
        setLoadMoreError(null);
      })
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Conversations could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [interactionStatus, interactionType, retryKey, search]);

  const companiesById = useMemo(
    () => new Map(companies.map((company) => [company.id, company])),
    [companies],
  );
  const contactNames = useMemo(
    () =>
      new Map(
        contacts.map((contact) => [
          contact.id,
          contact.firstName + " " + contact.lastName,
        ]),
      ),
    [contacts],
  );
  const accountGroups = useMemo(() => {
    const groups = new Map<string, Interaction[]>();
    for (const interaction of result?.items ?? []) {
      if (!interaction.companyId) continue;
      const existing = groups.get(interaction.companyId) ?? [];
      existing.push(interaction);
      groups.set(interaction.companyId, existing);
    }
    return [...groups].map(([companyId, interactions]) => ({
      company:
        companiesById.get(companyId) ??
        ({
          id: companyId,
          name: "Linked account",
          website: null,
          industry: null,
          location: null,
        } as AccountSummary),
      interactions,
    }));
  }, [companiesById, result]);
  const unassignedInteractions = useMemo(
    () => result?.items.filter((interaction) => !interaction.companyId) ?? [],
    [result],
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    beginReload();
    setSearch(searchDraft.trim());
  }

  function beginReload() {
    setLoading(true);
    setError(null);
    setLoadMoreError(null);
  }

  async function loadMore() {
    if (!result || result.page >= result.pages || loadingMore) return;
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const parameters = interactionParameters(
        search,
        interactionType,
        interactionStatus,
        result.page + 1,
      );
      const nextPage = await apiRequest<EntityPage<Interaction>>(
        "/api/v1/interactions?" + parameters.toString(),
      );
      const context = await hydrateLinkedContext(
        nextPage.items,
        companies,
        contacts,
      );
      setCompanies(context.companies);
      setContacts(context.contacts);
      setLoadedAt(Date.now());
      setResult((current) =>
        current
          ? {
              ...nextPage,
              items: mergeById(current.items, nextPage.items),
            }
          : nextPage,
      );
    } catch (requestError: unknown) {
      setLoadMoreError(
        requestError instanceof Error
          ? requestError.message
          : "More conversations could not be loaded.",
      );
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <section aria-labelledby="interactions-title">
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
            Relationship memory
          </p>
          <h1
            id="interactions-title"
            className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
          >
            Accounts
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            Open an account to see its shared conversation history, meeting
            notes and preparation in one place. General conversations remain
            available separately when no account is linked.
          </p>
        </div>
        <Link className="primary-button" href="/conversations/new">
          Add conversation
        </Link>
      </header>

      {!loading && !error && result ? (
        <ProviderCalendarContext interactions={result.items} />
      ) : null}

      <form
        role="search"
        onSubmit={submitSearch}
        className="mb-5 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-[minmax(0,1fr)_auto_auto_auto]"
      >
        <label className="sr-only" htmlFor="interaction-search">
          Search conversations
        </label>
        <input
          id="interaction-search"
          className="form-control"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="Search conversations"
        />
        <label className="sr-only" htmlFor="interaction-type-filter">
          Filter by type
        </label>
        <select
          id="interaction-type-filter"
          className="form-control"
          value={interactionType}
          onChange={(event) => {
            beginReload();
            setInteractionType(event.target.value as InteractionType | "");
          }}
        >
          <option value="">All types</option>
          {interactionTypes.map((value) => (
            <option key={value} value={value}>
              {humanise(value)}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="interaction-status-filter">
          Filter by status
        </label>
        <select
          id="interaction-status-filter"
          className="form-control"
          value={interactionStatus}
          onChange={(event) => {
            beginReload();
            setInteractionStatus(
              event.target.value as InteractionLifecycleStatus | "",
            );
          }}
        >
          <option value="">All statuses</option>
          {interactionStatuses.map((value) => (
            <option key={value} value={value}>
              {humanise(value)}
            </option>
          ))}
        </select>
        <button type="submit" className="secondary-button">
          Search
        </button>
      </form>

      {loading ? (
        <p role="status" className="rounded-2xl bg-white p-6 text-slate-600">
          Loading conversations…
        </p>
      ) : null}
      {!loading && error ? (
        <div
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 p-6"
        >
          <p className="text-sm text-red-900">{error}</p>
          <button
            type="button"
            className="secondary-button mt-4"
            onClick={() => {
              beginReload();
              setRetryKey((value) => value + 1);
            }}
          >
            Retry
          </button>
        </div>
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <h2 className="text-xl font-semibold text-slate-950">
            No conversations found
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Add a conversation or adjust the current filters.
          </p>
          <Link className="primary-button mt-5" href="/conversations/new">
            Add conversation
          </Link>
        </div>
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <div
          className={
            accountGroups.length > 0
              ? "grid gap-6 lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start"
              : "block"
          }
        >
          {accountGroups.length > 0 ? (
            <nav
              aria-label="Accounts in this view"
              className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm lg:sticky lg:top-6"
            >
              <p className="px-2 pb-2 text-xs font-bold uppercase tracking-[0.15em] text-slate-500">
                Accounts
              </p>
              <ul className="space-y-1">
                {accountGroups.map(({ company, interactions }) => (
                  <li key={company.id}>
                    <Link
                      className="flex items-center gap-3 rounded-xl px-2 py-2 text-sm font-semibold text-slate-800 hover:bg-brand-secondary/10 focus:outline-none focus:ring-2 focus:ring-brand-focus"
                      href={
                        "/conversations/accounts/" +
                        company.id +
                        "#conversations"
                      }
                    >
                      <AccountAvatar
                        accountId={company.id}
                        name={company.name}
                        website={company.website}
                        size="compact"
                      />
                      <span className="min-w-0 flex-1 truncate">
                        {company.name}
                      </span>
                      <span
                        aria-label={
                          interactions.length +
                          (interactions.length === 1
                            ? " conversation"
                            : " conversations")
                        }
                        className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                      >
                        {interactions.length}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              {unassignedInteractions.length > 0 ? (
                <a
                  className="mt-2 flex items-center justify-between rounded-xl px-2 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-focus"
                  href="#general-conversations"
                >
                  General
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                    {unassignedInteractions.length}
                  </span>
                </a>
              ) : null}
            </nav>
          ) : null}
          <div className="space-y-8">
            {accountGroups.length > 0 ? (
              <section aria-labelledby="account-conversations-title">
                <div className="mb-4">
                  <h2
                    id="account-conversations-title"
                    className="text-2xl font-semibold text-slate-950"
                  >
                    Account conversations
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">
                    {accountGroups.length}{" "}
                    {accountGroups.length === 1 ? "account" : "accounts"} in
                    this view
                  </p>
                </div>
                <div className="grid gap-4 xl:grid-cols-2">
                  {accountGroups.map(({ company, interactions }) => (
                    <AccountConversationCard
                      key={company.id}
                      company={company}
                      interactions={interactions}
                      referenceTime={loadedAt}
                    />
                  ))}
                </div>
              </section>
            ) : null}
            {unassignedInteractions.length > 0 ? (
              <section
                id="general-conversations"
                aria-labelledby="general-conversations-title"
                className="scroll-mt-6"
              >
                <h2
                  id="general-conversations-title"
                  className="text-2xl font-semibold text-slate-950"
                >
                  General and unassigned conversations
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  Conversations that are not yet part of an account history.
                </p>
                <div className="mt-4 grid gap-4 xl:grid-cols-2">
                  {unassignedInteractions.map((interaction) => (
                    <InteractionCard
                      key={interaction.id}
                      interaction={interaction}
                      companyName={null}
                      contactName={
                        interaction.contactId
                          ? (contactNames.get(interaction.contactId) ??
                            "Linked contact")
                          : null
                      }
                    />
                  ))}
                </div>
              </section>
            ) : null}
            {result.page < result.pages ? (
              <button
                type="button"
                className="secondary-button"
                disabled={loadingMore}
                onClick={() => void loadMore()}
              >
                {loadingMore ? "Loading more…" : "Load more conversations"}
              </button>
            ) : null}
            {loadMoreError ? (
              <p
                role="alert"
                className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
              >
                {loadMoreError}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function interactionParameters(
  search: string,
  interactionType: InteractionType | "",
  interactionStatus: InteractionLifecycleStatus | "",
  page = 1,
): URLSearchParams {
  const parameters = new URLSearchParams({
    page: String(page),
    pageSize: "100",
    sortBy: "start_at",
    sortOrder: "desc",
  });
  if (search) parameters.set("search", search);
  if (interactionType) parameters.set("interactionType", interactionType);
  if (interactionStatus) parameters.set("status", interactionStatus);
  return parameters;
}

async function hydrateLinkedContext(
  interactions: Interaction[],
  companies: Company[],
  contacts: Contact[],
  signal?: AbortSignal,
): Promise<{ companies: Company[]; contacts: Contact[] }> {
  const knownCompanyIds = new Set(companies.map((company) => company.id));
  const missingCompanyIds = [
    ...new Set(
      interactions
        .map((interaction) => interaction.companyId)
        .filter((value): value is string => Boolean(value)),
    ),
  ].filter((companyId) => !knownCompanyIds.has(companyId));
  const knownContactIds = new Set(contacts.map((contact) => contact.id));
  const missingContactIds = [
    ...new Set(
      interactions
        .map((interaction) => interaction.contactId)
        .filter((value): value is string => Boolean(value)),
    ),
  ].filter((contactId) => !knownContactIds.has(contactId));
  const [linkedCompanies, linkedContacts] = await Promise.all([
    Promise.all(
      missingCompanyIds.map((companyId) =>
        apiRequest<Company>(
          "/api/v1/companies/" + encodeURIComponent(companyId),
          signal ? { signal } : undefined,
        ),
      ),
    ),
    Promise.all(
      missingContactIds.map((contactId) =>
        apiRequest<Contact>(
          "/api/v1/contacts/" + encodeURIComponent(contactId),
          signal ? { signal } : undefined,
        ),
      ),
    ),
  ]);
  return {
    companies: mergeById(companies, linkedCompanies),
    contacts: mergeById(contacts, linkedContacts),
  };
}

function mergeById<T extends { id: string }>(
  current: T[],
  additions: T[],
): T[] {
  const merged = new Map(current.map((item) => [item.id, item]));
  for (const item of additions) merged.set(item.id, item);
  return [...merged.values()];
}

function AccountConversationCard({
  company,
  interactions,
  referenceTime,
}: {
  company: AccountSummary;
  interactions: Interaction[];
  referenceTime: number;
}) {
  const upcoming = interactions
    .filter((interaction) => {
      if (interaction.lifecycleStatus !== "planned") return false;
      if (interaction.scheduledStartAt === null) return false;
      return new Date(interaction.scheduledStartAt).getTime() >= referenceTime;
    })
    .sort(
      (left, right) =>
        new Date(left.scheduledStartAt ?? 0).getTime() -
        new Date(right.scheduledStartAt ?? 0).getTime(),
    )[0];
  const highlighted = upcoming ?? interactions[0];
  const preparedCount = interactions.filter(
    (interaction) => interaction.briefState === "completed",
  ).length;
  const context = [
    company.industry,
    company.location,
    websiteHost(company.website),
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <article className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-brand-secondary/40 hover:shadow-md">
      <div className="flex items-start gap-4">
        <AccountAvatar
          accountId={company.id}
          name={company.name}
          website={company.website}
        />
        <div className="min-w-0 flex-1">
          <h3 className="text-xl font-semibold text-slate-950">
            <Link
              className="rounded underline-offset-4 group-hover:underline focus:outline-none focus:ring-2 focus:ring-brand-focus"
              href={"/conversations/accounts/" + company.id + "#conversations"}
            >
              {company.name}
            </Link>
          </h3>
          {context ? (
            <p className="mt-1 truncate text-sm text-slate-600">{context}</p>
          ) : null}
          <p className="mt-3 text-sm font-semibold text-slate-700">
            {interactions.length}{" "}
            {interactions.length === 1 ? "conversation" : "conversations"}
            {preparedCount > 0 ? " · " + preparedCount + " prepared" : ""}
          </p>
        </div>
      </div>
      {highlighted ? (
        <div className="mt-5 border-t border-slate-100 pt-4">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
            {upcoming ? "Next conversation" : "Latest conversation"}
          </p>
          <Link
            className="mt-1 block font-semibold text-slate-950 underline-offset-4 hover:underline"
            href={"/conversations/" + highlighted.id}
          >
            {highlighted.title}
          </Link>
          <p className="mt-1 text-sm text-slate-600">
            {formatInteractionDate(
              highlighted.actualStartAt ?? highlighted.scheduledStartAt,
            )}
          </p>
        </div>
      ) : null}
      <Link
        className="mt-5 inline-flex text-sm font-bold text-brand-secondary underline-offset-4 hover:underline"
        href={"/conversations/accounts/" + company.id + "#conversations"}
      >
        View conversations and notes
      </Link>
    </article>
  );
}

function websiteHost(website: string | null): string | null {
  if (!website) return null;
  try {
    return new URL(
      website.startsWith("http://") || website.startsWith("https://")
        ? website
        : "https://" + website,
    ).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}
