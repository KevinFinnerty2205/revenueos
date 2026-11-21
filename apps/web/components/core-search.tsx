"use client";

import type {
  AskScopeType,
  Company,
  EntityPage,
  Interaction,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { AskRevenueOS } from "@/components/ask-revenueos";

interface SearchResults {
  companies: Company[];
  interactions: Interaction[];
}

interface SearchAvailability {
  companies: SearchSourceState;
  interactions: SearchSourceState;
}

type SearchSourceState = "pending" | "available" | "unavailable";

const emptyResults: SearchResults = {
  companies: [],
  interactions: [],
};

export function CoreSearch({
  initialMode = "search",
  scopeType = "workspace",
  scopeId = null,
  initialQuestion = "",
}: {
  initialMode?: "search" | "ask";
  scopeType?: AskScopeType;
  scopeId?: string | null;
  initialQuestion?: string;
}) {
  const [mode, setMode] = useState<"search" | "ask">(initialMode);
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [results, setResults] = useState<SearchResults>(emptyResults);
  const [availability, setAvailability] = useState<SearchAvailability | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeQuery, setActiveQuery] = useState<string | null>(null);
  const searchGeneration = useRef(0);
  const activeSearch = useRef<{
    controller: AbortController;
    query: string;
  } | null>(null);

  useEffect(
    () => () => {
      searchGeneration.current += 1;
      activeSearch.current?.controller.abort();
      activeSearch.current = null;
    },
    [],
  );

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    if (value.length < 2) {
      searchGeneration.current += 1;
      activeSearch.current?.controller.abort();
      activeSearch.current = null;
      setActiveQuery(null);
      setLoading(false);
      setResults(emptyResults);
      setAvailability(null);
      setSubmittedQuery("");
      setError("Enter at least two characters to search.");
      return;
    }
    if (activeSearch.current?.query === value) return;

    const generation = searchGeneration.current + 1;
    searchGeneration.current = generation;
    activeSearch.current?.controller.abort();
    const controller = new AbortController();
    activeSearch.current = { controller, query: value };
    setActiveQuery(value);
    const sourceState: SearchAvailability = {
      companies: "pending",
      interactions: "pending",
    };
    let settledSources = 0;
    setLoading(true);
    setError(null);
    setResults(emptyResults);
    setAvailability({ ...sourceState });
    setSubmittedQuery(value);
    const encoded = encodeURIComponent(value);

    function settleSource(
      source: keyof SearchAvailability,
      state: Exclude<SearchSourceState, "pending">,
      items: Company[] | Interaction[] = [],
    ) {
      if (generation !== searchGeneration.current) return;
      sourceState[source] = state;
      settledSources += 1;
      setResults((current) => ({
        ...current,
        [source]: state === "available" ? items : [],
      }));
      setAvailability({ ...sourceState });
      if (settledSources < 2) return;

      if (activeSearch.current?.controller === controller) {
        activeSearch.current = null;
        setActiveQuery(null);
      }
      setLoading(false);
      if (
        sourceState.companies === "unavailable" &&
        sourceState.interactions === "unavailable"
      ) {
        setResults(emptyResults);
        setAvailability(null);
        setSubmittedQuery("");
        setError("Search could not be completed. Please try again.");
      }
    }

    void apiRequest<EntityPage<Company>>(
      `/api/v1/companies?page=1&pageSize=6&search=${encoded}`,
      { signal: controller.signal },
    ).then(
      (companies) => settleSource("companies", "available", companies.items),
      () => settleSource("companies", "unavailable"),
    );
    void apiRequest<EntityPage<Interaction>>(
      `/api/v1/interactions?page=1&pageSize=6&sortBy=start_at&sortOrder=desc&search=${encoded}`,
      { signal: controller.signal },
    ).then(
      (interactions) =>
        settleSource("interactions", "available", interactions.items),
      () => settleSource("interactions", "unavailable"),
    );
  }

  const resultCount = results.companies.length + results.interactions.length;
  const partialResults =
    availability !== null &&
    (availability.companies === "unavailable" ||
      availability.interactions === "unavailable");
  const pendingResults =
    availability !== null &&
    (availability.companies === "pending" ||
      availability.interactions === "pending");
  const incompleteResults = partialResults || pendingResults;
  const noSourcesSettled =
    availability?.companies === "pending" &&
    availability.interactions === "pending";
  const searchingCurrentQuery = loading && activeQuery === query.trim();

  if (mode === "ask") {
    return (
      <div className="space-y-6">
        <SearchModeTabs mode={mode} onChange={setMode} />
        <div id="ask-mode-panel" role="tabpanel" aria-labelledby="ask-mode-tab">
          <AskRevenueOS
            scopeType={scopeType}
            scopeId={scopeId}
            initialQuestion={initialQuestion}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SearchModeTabs mode={mode} onChange={setMode} />
      <div
        id="search-mode-panel"
        role="tabpanel"
        aria-labelledby="search-mode-tab"
        className="space-y-6"
      >
        <form onSubmit={search} className="form-card">
          <label htmlFor="core-search" className="form-label">
            Search your workspace
          </label>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Find a conversation by title, relationship, transcript or your
            private notes, or open an account’s conversation history.
          </p>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <input
              id="core-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="form-input flex-1"
              placeholder="Try a conversation, private note or account"
              autoComplete="off"
            />
            <button
              type="submit"
              className="primary-button"
              disabled={searchingCurrentQuery}
            >
              {searchingCurrentQuery ? "Searching…" : "Search"}
            </button>
          </div>
          {error ? (
            <p role="alert" className="mt-4 text-sm text-rose-800">
              {error}
            </p>
          ) : null}
        </form>

        {submittedQuery ? (
          <section aria-labelledby="search-results-title" className="space-y-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
                {noSourcesSettled ? (
                  "Search in progress"
                ) : (
                  <>
                    {resultCount} {incompleteResults ? "available " : ""}
                    {resultCount === 1 ? "result" : "results"}
                  </>
                )}
              </p>
              <h2
                id="search-results-title"
                className="mt-1 text-2xl font-semibold"
              >
                Results for “{submittedQuery}”
              </h2>
            </div>
            {availability?.companies === "pending" ? (
              <p role="status" className="text-sm text-slate-600">
                Searching account results…
              </p>
            ) : null}
            {availability?.interactions === "pending" ? (
              <p role="status" className="text-sm text-slate-600">
                Searching conversation results…
              </p>
            ) : null}
            {availability?.companies === "unavailable" ? (
              <p
                role="status"
                className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950"
              >
                Account results are temporarily unavailable. Conversation
                results are shown when available.
              </p>
            ) : null}
            {availability?.interactions === "unavailable" ? (
              <p
                role="status"
                className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950"
              >
                Conversation results are temporarily unavailable. Account
                results are shown when available.
              </p>
            ) : null}
            {resultCount === 0 && !incompleteResults ? (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6">
                <h3 className="font-semibold text-slate-950">
                  No matching work found
                </h3>
                <p className="mt-2 text-sm text-slate-600">
                  Check the spelling or try a shorter phrase from a
                  conversation, your private notes or an account name.
                </p>
              </div>
            ) : resultCount > 0 ? (
              <div className="grid gap-4">
                <ResultGroup
                  title="Conversations"
                  items={results.interactions.map((interaction) => ({
                    href: `/conversations/${interaction.id}`,
                    title: interaction.title,
                    detail: `${humanise(interaction.interactionType)} · ${humanise(
                      interaction.lifecycleStatus,
                    )}`,
                  }))}
                />
                <ResultGroup
                  title="Accounts"
                  items={results.companies.map((company) => ({
                    href: `/conversations/accounts/${company.id}`,
                    title: company.name,
                    detail: company.industry ?? "Account",
                  }))}
                />
              </div>
            ) : null}
          </section>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm leading-6 text-slate-600">
            Start with the conversation or relationship you want to remember.
            Recent work remains on Home and in conversation history.
          </div>
        )}
      </div>
    </div>
  );
}

function SearchModeTabs({
  mode,
  onChange,
}: {
  mode: "search" | "ask";
  onChange: (mode: "search" | "ask") => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Search or Ask Oryntela"
      className="inline-flex rounded-2xl border border-slate-200 bg-white p-1 shadow-sm"
    >
      <button
        id="search-mode-tab"
        type="button"
        role="tab"
        aria-selected={mode === "search"}
        tabIndex={mode === "search" ? 0 : -1}
        aria-controls="search-mode-panel"
        onClick={() => onChange("search")}
        onKeyDown={(event) => changeTabFromKeyboard(event, mode, onChange)}
        data-search-mode="search"
        className={`min-h-11 rounded-xl px-5 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-brand-focus ${
          mode === "search" ? "bg-brand-primary text-white" : "text-slate-600"
        }`}
      >
        Search
      </button>
      <button
        id="ask-mode-tab"
        type="button"
        role="tab"
        aria-selected={mode === "ask"}
        tabIndex={mode === "ask" ? 0 : -1}
        aria-controls="ask-mode-panel"
        onClick={() => onChange("ask")}
        onKeyDown={(event) => changeTabFromKeyboard(event, mode, onChange)}
        data-search-mode="ask"
        className={`min-h-11 rounded-xl px-5 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-brand-focus ${
          mode === "ask" ? "bg-brand-primary text-white" : "text-slate-600"
        }`}
      >
        Ask Oryntela
      </button>
    </div>
  );
}

function changeTabFromKeyboard(
  event: KeyboardEvent<HTMLButtonElement>,
  mode: "search" | "ask",
  onChange: (mode: "search" | "ask") => void,
) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const tablist = event.currentTarget.parentElement;
  const nextMode =
    event.key === "Home"
      ? "search"
      : event.key === "End"
        ? "ask"
        : mode === "search"
          ? "ask"
          : "search";
  onChange(nextMode);
  const selector = `[data-search-mode="${nextMode}"]`;
  window.requestAnimationFrame(() =>
    tablist?.querySelector<HTMLButtonElement>(selector)?.focus(),
  );
}

function ResultGroup({
  title,
  items,
}: {
  title: string;
  items: Array<{ href: string; title: string; detail: string }>;
}) {
  if (!items.length) return null;
  return (
    <section className="form-card" aria-label={title}>
      <h3 className="form-legend">{title}</h3>
      <ul className="mt-4 divide-y divide-slate-100">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="group flex min-h-16 items-center justify-between gap-4 rounded-xl px-2 py-3 focus:outline-none focus:ring-2 focus:ring-brand-focus"
            >
              <span>
                <span className="block font-semibold text-slate-950 group-hover:text-brand-secondary">
                  {item.title}
                </span>
                <span className="mt-1 block text-sm text-slate-600">
                  {item.detail}
                </span>
              </span>
              <span aria-hidden="true" className="text-brand-secondary">
                →
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function humanise(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}
