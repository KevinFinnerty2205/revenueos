"use client";

import type {
  AskScopeType,
  Company,
  Contact,
  EntityPage,
  Interaction,
  OpportunityListItem,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, KeyboardEvent, useState } from "react";
import { apiRequest } from "@/lib/api";
import { AskRevenueOS } from "@/components/ask-revenueos";

interface SearchResults {
  companies: Company[];
  contacts: Contact[];
  opportunities: OpportunityListItem[];
  interactions: Interaction[];
}

const emptyResults: SearchResults = {
  companies: [],
  contacts: [],
  opportunities: [],
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    if (value.length < 2) {
      setError("Enter at least two characters to search.");
      return;
    }

    setLoading(true);
    setError(null);
    const encoded = encodeURIComponent(value);
    try {
      const [companies, contacts, opportunities, interactions] =
        await Promise.all([
          apiRequest<EntityPage<Company>>(
            `/api/v1/companies?page=1&pageSize=6&search=${encoded}`,
          ),
          apiRequest<EntityPage<Contact>>(
            `/api/v1/contacts?page=1&pageSize=6&search=${encoded}`,
          ),
          apiRequest<EntityPage<OpportunityListItem>>(
            `/api/v1/opportunities?page=1&pageSize=6&search=${encoded}`,
          ),
          apiRequest<EntityPage<Interaction>>(
            `/api/v1/interactions?page=1&pageSize=6&sortBy=start_at&sortOrder=desc&search=${encoded}`,
          ),
        ]);
      setResults({
        companies: companies.items,
        contacts: contacts.items,
        opportunities: opportunities.items,
        interactions: interactions.items,
      });
      setSubmittedQuery(value);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Search could not be completed.",
      );
    } finally {
      setLoading(false);
    }
  }

  const resultCount =
    results.companies.length +
    results.contacts.length +
    results.opportunities.length +
    results.interactions.length;

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
        <form onSubmit={(event) => void search(event)} className="form-card">
          <label htmlFor="core-search" className="form-label">
            Search your workspace
          </label>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Find an account, contact, opportunity or interaction. Search stays
            inside your organisation and does not generate an AI answer.
          </p>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <input
              id="core-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="form-input flex-1"
              placeholder="Try an account or deal name"
              autoComplete="off"
            />
            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? "Searching…" : "Search"}
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
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
                {resultCount} {resultCount === 1 ? "result" : "results"}
              </p>
              <h2
                id="search-results-title"
                className="mt-1 text-2xl font-semibold"
              >
                Results for “{submittedQuery}”
              </h2>
            </div>
            {resultCount === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6">
                <h3 className="font-semibold text-slate-950">
                  No matching work found
                </h3>
                <p className="mt-2 text-sm text-slate-600">
                  Check the spelling or search using a shorter account, deal or
                  interaction name.
                </p>
              </div>
            ) : (
              <div className="grid gap-4">
                <ResultGroup
                  title="Contacts"
                  items={results.contacts.map((contact) => ({
                    href: `/contacts/${contact.id}`,
                    title: `${contact.firstName} ${contact.lastName}`,
                    detail: contact.email ?? contact.jobTitle ?? "Contact",
                  }))}
                />
                <ResultGroup
                  title="Accounts"
                  items={results.companies.map((company) => ({
                    href: `/companies/${company.id}`,
                    title: company.name,
                    detail: company.industry ?? "Account",
                  }))}
                />
                <ResultGroup
                  title="Opportunities"
                  items={results.opportunities.map((opportunity) => ({
                    href: `/opportunities/${opportunity.id}`,
                    title: opportunity.name,
                    detail: opportunity.companyName
                      ? `${opportunity.companyName} · ${humanise(opportunity.stage)}`
                      : humanise(opportunity.stage),
                  }))}
                />
                <ResultGroup
                  title="Interactions"
                  items={results.interactions.map((interaction) => ({
                    href: `/interactions/${interaction.id}`,
                    title: interaction.title,
                    detail: `${humanise(interaction.interactionType)} · ${humanise(
                      interaction.lifecycleStatus,
                    )}`,
                  }))}
                />
              </div>
            )}
          </section>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm leading-6 text-slate-600">
            Start with the customer or deal you want to move forward. Recent
            work remains on Home and your interaction timeline.
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
      aria-label="Search or Ask RevenueOS"
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
        className={`min-h-11 rounded-xl px-5 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-teal-600 ${
          mode === "search" ? "bg-slate-950 text-white" : "text-slate-600"
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
        className={`min-h-11 rounded-xl px-5 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-teal-600 ${
          mode === "ask" ? "bg-slate-950 text-white" : "text-slate-600"
        }`}
      >
        Ask RevenueOS
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
              className="group flex min-h-16 items-center justify-between gap-4 rounded-xl px-2 py-3 focus:outline-none focus:ring-2 focus:ring-teal-600"
            >
              <span>
                <span className="block font-semibold text-slate-950 group-hover:text-teal-800">
                  {item.title}
                </span>
                <span className="mt-1 block text-sm text-slate-600">
                  {item.detail}
                </span>
              </span>
              <span aria-hidden="true" className="text-teal-700">
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
