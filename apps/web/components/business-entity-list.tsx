"use client";

import type {
  Company,
  Contact,
  EntityPage,
  Opportunity,
  Task,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import {
  type BusinessEntityName,
  entityLabels,
  humanise,
} from "@/lib/business-entities";

type BusinessEntity = Company | Contact | Opportunity | Task;

interface DisplayCell {
  label: string;
  value: ReactNode;
}

const filterOptions: Partial<
  Record<
    BusinessEntityName,
    { label: string; plural: string; values: string[] }
  >
> = {
  companies: {
    label: "Status",
    plural: "statuses",
    values: ["prospect", "active", "inactive"],
  },
  opportunities: {
    label: "Stage",
    plural: "stages",
    values: [
      "discovery",
      "qualification",
      "proposal",
      "negotiation",
      "closed_won",
      "closed_lost",
    ],
  },
  tasks: {
    label: "Status",
    plural: "statuses",
    values: ["open", "in_progress", "completed", "cancelled"],
  },
};

export function BusinessEntityList({ entity }: { entity: BusinessEntityName }) {
  const labels = entityLabels[entity];
  const filterConfig = filterOptions[entity];
  const [result, setResult] = useState<EntityPage<BusinessEntity> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [page, setPage] = useState(1);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const parameters = new URLSearchParams({
      page: String(page),
      pageSize: "20",
    });
    if (search) {
      parameters.set("search", search);
    }
    if (filter) {
      parameters.set(entity === "opportunities" ? "stage" : "status", filter);
    }

    apiRequest<EntityPage<BusinessEntity>>(
      `/api/v1/${entity}?${parameters.toString()}`,
      { signal: controller.signal },
    )
      .then(setResult)
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
            : "The records could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [entity, filter, page, retryKey, search]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setPage(1);
    setSearch(searchDraft.trim());
  }

  return (
    <section aria-labelledby={`${entity}-title`}>
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            {labels.eyebrow}
          </p>
          <h1
            id={`${entity}-title`}
            className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
          >
            {labels.plural}
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            {labels.description}
          </p>
        </div>
        <Link
          href={`/${entity}/new`}
          className="inline-flex min-h-11 items-center justify-center rounded-xl bg-teal-700 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
        >
          Create {labels.singular}
        </Link>
      </header>

      <form
        onSubmit={submitSearch}
        className="mb-5 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-[minmax(0,1fr)_auto_auto]"
        role="search"
      >
        <label className="sr-only" htmlFor={`${entity}-search`}>
          Search {labels.plural.toLowerCase()}
        </label>
        <input
          id={`${entity}-search`}
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder={`Search ${labels.plural.toLowerCase()}`}
          className="min-h-11 rounded-xl border border-slate-300 px-4 text-sm outline-none transition focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
        />
        {filterConfig ? (
          <>
            <label className="sr-only" htmlFor={`${entity}-filter`}>
              Filter by {filterConfig.label.toLowerCase()}
            </label>
            <select
              id={`${entity}-filter`}
              value={filter}
              onChange={(event) => {
                setLoading(true);
                setError(null);
                setPage(1);
                setFilter(event.target.value);
              }}
              className="min-h-11 rounded-xl border border-slate-300 bg-white px-4 text-sm outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
            >
              <option value="">All {filterConfig.plural}</option>
              {filterConfig.values.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
          </>
        ) : null}
        <button
          type="submit"
          className="min-h-11 rounded-xl border border-slate-300 bg-slate-50 px-5 text-sm font-bold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
        >
          Search
        </button>
      </form>

      {loading ? <LoadingState label={labels.plural} /> : null}
      {!loading && error ? (
        <ErrorState
          message={error}
          onRetry={() => {
            setLoading(true);
            setError(null);
            setRetryKey((key) => key + 1);
          }}
        />
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <EmptyList entity={entity} />
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <>
          <EntityRows entity={entity} items={result.items} />
          <nav
            aria-label={`${labels.plural} pagination`}
            className="mt-5 flex items-center justify-between gap-4"
          >
            <p className="text-sm text-slate-600">
              Page {result.page} of {result.pages}
            </p>
            <div className="flex gap-2">
              <PaginationButton
                label="Previous"
                disabled={result.page <= 1}
                onClick={() => {
                  setLoading(true);
                  setPage((current) => Math.max(1, current - 1));
                }}
              />
              <PaginationButton
                label="Next"
                disabled={result.page >= result.pages}
                onClick={() => {
                  setLoading(true);
                  setPage((current) => current + 1);
                }}
              />
            </div>
          </nav>
        </>
      ) : null}
    </section>
  );
}

function EntityRows({
  entity,
  items,
}: {
  entity: BusinessEntityName;
  items: BusinessEntity[];
}) {
  const rows = items.map((item) => ({
    id: item.id,
    cells: displayCells(entity, item),
  }));
  const labels = rows[0]?.cells.map((cell) => cell.label) ?? [];

  return (
    <>
      <div className="space-y-3 md:hidden">
        {rows.map((row) => (
          <article
            key={row.id}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <dl className="space-y-3">
              {row.cells.map((cell) => (
                <div key={cell.label}>
                  <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                    {cell.label}
                  </dt>
                  <dd className="mt-1 break-words text-sm text-slate-900">
                    {cell.value}
                  </dd>
                </div>
              ))}
            </dl>
            <Link
              href={`/${entity}/${row.id}/edit`}
              className="mt-5 inline-flex text-sm font-bold text-teal-700 hover:text-teal-900"
            >
              Edit {entityLabels[entity].singular}
            </Link>
          </article>
        ))}
      </div>
      <div className="hidden overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm md:block">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                {labels.map((label) => (
                  <th key={label} scope="col" className="px-5 py-4 font-bold">
                    {label}
                  </th>
                ))}
                <th scope="col" className="px-5 py-4 text-right font-bold">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50/70">
                  {row.cells.map((cell) => (
                    <td
                      key={cell.label}
                      className="max-w-xs px-5 py-4 text-slate-700"
                    >
                      {cell.value}
                    </td>
                  ))}
                  <td className="px-5 py-4 text-right">
                    <Link
                      href={`/${entity}/${row.id}/edit`}
                      className="font-bold text-teal-700 hover:text-teal-900"
                    >
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function displayCells(
  entity: BusinessEntityName,
  item: BusinessEntity,
): DisplayCell[] {
  if (entity === "companies") {
    const company = item as Company;
    return [
      { label: "Name", value: company.name },
      { label: "Industry", value: company.industry ?? "—" },
      { label: "Status", value: humanise(company.status) },
      {
        label: "Employees",
        value: company.employeeCount?.toLocaleString("en-AU") ?? "—",
      },
    ];
  }
  if (entity === "contacts") {
    const contact = item as Contact;
    return [
      {
        label: "Name",
        value: `${contact.firstName} ${contact.lastName}`,
      },
      { label: "Email", value: contact.email },
      { label: "Job title", value: contact.jobTitle ?? "—" },
      { label: "Phone", value: contact.phone ?? "—" },
    ];
  }
  if (entity === "opportunities") {
    const opportunity = item as Opportunity;
    return [
      { label: "Name", value: opportunity.name },
      { label: "Stage", value: humanise(opportunity.stage) },
      {
        label: "Value",
        value: formatCurrency(opportunity.value, opportunity.currency),
      },
      { label: "Probability", value: `${opportunity.probability}%` },
    ];
  }
  const task = item as Task;
  return [
    { label: "Title", value: task.title },
    { label: "Status", value: humanise(task.status) },
    { label: "Priority", value: humanise(task.priority) },
    { label: "Due", value: formatDate(task.dueAt) },
  ];
}

function formatCurrency(value: string, currency: string): string {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
  }).format(Number(value));
}

function formatDate(value: string | null): string {
  if (!value) {
    return "No due date";
  }
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function LoadingState({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
    >
      <p className="font-semibold text-slate-700">
        Loading {label.toLowerCase()}…
      </p>
      <div className="mt-5 space-y-3" aria-hidden="true">
        {[0, 1, 2].map((item) => (
          <div
            key={item}
            className="h-10 animate-pulse rounded-lg bg-slate-100"
          />
        ))}
      </div>
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-2xl border border-rose-200 bg-rose-50 p-6"
    >
      <h2 className="font-bold text-rose-950">Records could not be loaded</h2>
      <p className="mt-2 text-sm text-rose-800">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-lg bg-rose-900 px-4 py-2 text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-rose-700 focus:ring-offset-2"
      >
        Retry
      </button>
    </div>
  );
}

function EmptyList({ entity }: { entity: BusinessEntityName }) {
  const labels = entityLabels[entity];
  return (
    <div className="rounded-3xl border border-dashed border-slate-300 bg-white/70 p-8 shadow-sm sm:p-12">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
        Nothing here yet
      </p>
      <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">
        No {labels.plural.toLowerCase()} found
      </h2>
      <p className="mt-3 text-sm leading-7 text-slate-600">
        Create your first {labels.singular} to start building this workspace.
      </p>
    </div>
  );
}

function PaginationButton({
  label,
  disabled,
  onClick,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="min-h-10 rounded-lg border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {label}
    </button>
  );
}
