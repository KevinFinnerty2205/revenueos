"use client";

import type {
  EntityPage,
  OpportunityListItem,
  OpportunityStage,
  OpportunityStatus,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";

const stages: OpportunityStage[] = [
  "qualification",
  "discovery",
  "evaluation",
  "proposal",
  "negotiation",
  "procurement",
  "closed_won",
  "closed_lost",
  "other",
];
const statuses: OpportunityStatus[] = ["open", "won", "lost", "on_hold"];

export function OpportunityList() {
  const [result, setResult] = useState<EntityPage<OpportunityListItem> | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [status, setStatus] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const parameters = new URLSearchParams({
      page: String(page),
      pageSize: "20",
      sortBy: "updated_at",
      sortOrder: "desc",
    });
    if (search) parameters.set("search", search);
    if (stage) parameters.set("stage", stage);
    if (status) parameters.set("status", status);
    apiRequest<EntityPage<OpportunityListItem>>(
      `/api/v1/opportunities?${parameters.toString()}`,
      { signal: controller.signal },
    )
      .then((response) => {
        setResult(response);
        setError(null);
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
            : "Opportunities could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [page, refreshKey, search, stage, status]);

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setPage(1);
    setSearch(searchDraft.trim());
  }

  return (
    <section aria-labelledby="opportunities-title">
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Pipeline
          </p>
          <h1
            id="opportunities-title"
            className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
          >
            Opportunities
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            See commercial context, the latest meeting evidence and the next
            recommended move in one place.
          </p>
        </div>
        <Link href="/opportunities/new" className="primary-button">
          Create opportunity
        </Link>
      </header>

      <form
        role="search"
        onSubmit={applySearch}
        className="mb-5 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[minmax(12rem,1fr)_auto_auto_auto]"
      >
        <label className="sr-only" htmlFor="opportunity-search">
          Search opportunities
        </label>
        <input
          id="opportunity-search"
          className="form-control"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="Search opportunities"
        />
        <Filter
          id="opportunity-stage"
          label="Stage"
          value={stage}
          values={stages}
          onChange={(value) => {
            setLoading(true);
            setPage(1);
            setStage(value);
          }}
        />
        <Filter
          id="opportunity-status"
          label="Status"
          value={status}
          values={statuses}
          onChange={(value) => {
            setLoading(true);
            setPage(1);
            setStatus(value);
          }}
        />
        <button type="submit" className="secondary-button">
          Search
        </button>
      </form>

      {loading ? (
        <div role="status" className="form-card">
          Loading opportunities…
        </div>
      ) : null}
      {!loading && error ? (
        <div role="alert" className="form-card border-rose-200 bg-rose-50">
          <h2 className="font-bold text-rose-950">
            Opportunities could not be loaded
          </h2>
          <p className="mt-2 text-sm text-rose-800">{error}</p>
          <button
            type="button"
            className="mt-4 rounded-lg bg-rose-900 px-4 py-2 text-sm font-bold text-white"
            onClick={() => {
              setLoading(true);
              setRefreshKey((value) => value + 1);
            }}
          >
            Try again
          </button>
        </div>
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <div className="form-card text-center">
          <h2 className="text-xl font-semibold text-slate-950">
            No opportunities yet
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">
            Create an opportunity, then associate meetings to bring the latest
            validated meeting evidence into its workspace.
          </p>
          <Link href="/opportunities/new" className="primary-button mt-5">
            Create opportunity
          </Link>
        </div>
      ) : null}
      {!loading && !error && result?.items.length ? (
        <>
          <OpportunityRows items={result.items} />
          <nav
            aria-label="Opportunities pagination"
            className="mt-5 flex items-center justify-between gap-4"
          >
            <p className="text-sm text-slate-600">
              Page {result.page} of {result.pages}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className="secondary-button"
                disabled={result.page <= 1}
                onClick={() => {
                  setLoading(true);
                  setPage((value) => Math.max(1, value - 1));
                }}
              >
                Previous
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={result.page >= result.pages}
                onClick={() => {
                  setLoading(true);
                  setPage((value) => value + 1);
                }}
              >
                Next
              </button>
            </div>
          </nav>
        </>
      ) : null}
    </section>
  );
}

function Filter({
  id,
  label,
  value,
  values,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  values: readonly string[];
  onChange: (value: string) => void;
}) {
  return (
    <>
      <label className="sr-only" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="form-control w-full"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">All {label.toLowerCase()}s</option>
        {values.map((option) => (
          <option key={option} value={option}>
            {humanise(option)}
          </option>
        ))}
      </select>
    </>
  );
}

function OpportunityRows({ items }: { items: OpportunityListItem[] }) {
  return (
    <div className="grid gap-4">
      {items.map((opportunity) => (
        <article
          key={opportunity.id}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-teal-200 sm:p-6"
        >
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-bold text-teal-800">
                  {humanise(opportunity.stage)}
                </span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
                  {humanise(opportunity.status)}
                </span>
              </div>
              <h2 className="mt-3 text-xl font-semibold text-slate-950">
                <Link
                  href={`/opportunities/${opportunity.id}`}
                  className="rounded-sm hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600"
                >
                  {opportunity.name}
                </Link>
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                {opportunity.companyName ?? "No company"}
              </p>
            </div>
            <dl className="grid shrink-0 grid-cols-2 gap-x-7 gap-y-3 text-sm sm:grid-cols-3">
              <Detail label="Value">
                {formatCurrency(
                  opportunity.estimatedValue,
                  opportunity.currency,
                )}
              </Detail>
              <Detail label="Expected close">
                {formatDate(opportunity.expectedCloseDate)}
              </Detail>
              <Detail label="Updated">
                {formatMeetingDate(opportunity.updatedAt)}
              </Detail>
            </dl>
          </div>
          <div className="mt-5 grid gap-4 border-t border-slate-100 pt-5 lg:grid-cols-3">
            <Signal label="Latest meeting">
              {opportunity.latestMeetingDate
                ? formatMeetingDate(opportunity.latestMeetingDate)
                : "No meetings associated"}
            </Signal>
            <Signal label="Latest meeting momentum">
              {opportunity.latestMeetingMomentum
                ? humanise(opportunity.latestMeetingMomentum)
                : "Not available"}
            </Signal>
            <Signal label="Latest Next Best Action">
              {opportunity.latestNextBestAction ?? "Not available"}
            </Signal>
          </div>
        </article>
      ))}
    </div>
  );
}

function Detail({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-slate-800">{children}</dd>
    </div>
  );
}

function Signal({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-800">
        {children}
      </p>
    </div>
  );
}

function formatCurrency(value: string | null, currency: string | null) {
  if (!value || !currency) return "Not set";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
  }).format(Number(value));
}

function formatDate(value: string | null) {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
}
