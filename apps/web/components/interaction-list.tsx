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
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import {
  formatInteractionDate,
  interactionStatuses,
  interactionTypes,
} from "@/lib/interactions";

export function InteractionList() {
  const [result, setResult] = useState<EntityPage<Interaction> | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
    const parameters = new URLSearchParams({
      pageSize: "100",
      sortBy: "start_at",
      sortOrder: "desc",
    });
    if (search) parameters.set("search", search);
    if (interactionType) parameters.set("interactionType", interactionType);
    if (interactionStatus) parameters.set("status", interactionStatus);
    Promise.all([
      apiRequest<EntityPage<Interaction>>(
        `/api/v1/interactions?${parameters.toString()}`,
        { signal: controller.signal },
      ),
      apiRequest<EntityPage<Company>>("/api/v1/companies?pageSize=100", {
        signal: controller.signal,
      }),
      apiRequest<EntityPage<Contact>>("/api/v1/contacts?pageSize=100", {
        signal: controller.signal,
      }),
    ])
      .then(([interactions, companyPage, contactPage]) => {
        setResult(interactions);
        setCompanies(companyPage.items);
        setContacts(contactPage.items);
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
            : "Interactions could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [interactionStatus, interactionType, retryKey, search]);

  const companyNames = useMemo(
    () => new Map(companies.map((company) => [company.id, company.name])),
    [companies],
  );
  const contactNames = useMemo(
    () =>
      new Map(
        contacts.map((contact) => [
          contact.id,
          `${contact.firstName} ${contact.lastName}`,
        ]),
      ),
    [contacts],
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    beginReload();
    setSearch(searchDraft.trim());
  }

  function beginReload() {
    setLoading(true);
    setError(null);
  }

  return (
    <section aria-labelledby="interactions-title">
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Customer activity
          </p>
          <h1
            id="interactions-title"
            className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
          >
            Interactions
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            Keep phone calls, customer meetings, workshops, presentations and
            field activity in one timeline. Existing Meeting Intelligence
            remains available from each linked meeting.
          </p>
        </div>
        <Link className="primary-button" href="/interactions/new">
          Create interaction
        </Link>
      </header>

      <form
        role="search"
        onSubmit={submitSearch}
        className="mb-5 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-[minmax(0,1fr)_auto_auto_auto]"
      >
        <label className="sr-only" htmlFor="interaction-search">
          Search interactions
        </label>
        <input
          id="interaction-search"
          className="form-control"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="Search interactions"
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
          Loading interactions…
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
            No interactions found
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Create an interaction or adjust the current filters.
          </p>
          <Link className="primary-button mt-5" href="/interactions/new">
            Create interaction
          </Link>
        </div>
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {result.items.map((interaction) => (
            <article
              key={interaction.id}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wide">
                <span className="rounded-full bg-teal-50 px-3 py-1 text-teal-800">
                  {humanise(interaction.interactionType)}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
                  {humanise(interaction.lifecycleStatus)}
                </span>
                <span
                  className={`rounded-full px-3 py-1 ${
                    interaction.briefState === "completed"
                      ? "bg-emerald-50 text-emerald-800"
                      : interaction.briefState === "not_generated"
                        ? "bg-amber-50 text-amber-900"
                        : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {interaction.briefState === "completed"
                    ? "Brief ready"
                    : interaction.briefState === "not_generated"
                      ? "Not prepared"
                      : "Link context"}
                </span>
                {interaction.interactionType === "phone_call" ? (
                  <span className="rounded-full bg-indigo-50 px-3 py-1 text-indigo-800">
                    {humanise(interaction.callDirection ?? "unknown")}
                  </span>
                ) : null}
              </div>
              <h2 className="mt-4 text-xl font-semibold text-slate-950">
                <Link
                  className="rounded focus:outline-none focus:ring-2 focus:ring-teal-600"
                  href={`/interactions/${interaction.id}`}
                >
                  {interaction.title}
                </Link>
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                {formatInteractionDate(
                  interaction.actualStartAt ?? interaction.scheduledStartAt,
                )}
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {interaction.companyId
                  ? (companyNames.get(interaction.companyId) ??
                    "Linked company")
                  : "No company linked"}
              </p>
              {interaction.interactionType === "phone_call" ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
                  <span>
                    {interaction.contactId
                      ? (contactNames.get(interaction.contactId) ??
                        "Linked contact")
                      : "No contact linked"}
                  </span>
                  {interaction.durationSeconds !== null &&
                  interaction.durationSeconds !== undefined ? (
                    <span>· {formatDuration(interaction.durationSeconds)}</span>
                  ) : null}
                  {interaction.callOutcome ? (
                    <span>· {humanise(interaction.callOutcome)}</span>
                  ) : null}
                </div>
              ) : null}
              {interaction.interactionType === "phone_call" ||
              interaction.captureMethods?.length ? (
                <p className="mt-3 text-xs font-semibold text-teal-800">
                  Capture:{" "}
                  {interaction.captureMethods?.length
                    ? interaction.captureMethods.map(humanise).join(" · ")
                    : "None yet"}
                  {interaction.intelligenceState
                    ? ` · Intelligence ${humanise(interaction.intelligenceState).toLowerCase()}`
                    : ""}
                  {interaction.recordingAvailable
                    ? " · Recording available"
                    : ""}
                </p>
              ) : null}
              {interaction.meetingId ? (
                <Link
                  className="mt-4 inline-block text-sm font-bold text-teal-800 underline-offset-4 hover:underline"
                  href={`/meetings/${interaction.meetingId}`}
                >
                  Open Meeting Intelligence
                </Link>
              ) : null}
              {interaction.briefState !== "unavailable" ? (
                <Link
                  className="mt-4 ml-4 inline-block text-sm font-bold text-teal-800 underline-offset-4 hover:underline"
                  href={`/interactions/${interaction.id}#preparation`}
                >
                  {interaction.briefState === "completed"
                    ? "Open brief"
                    : "Prepare brief"}
                </Link>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m${seconds % 60 ? ` ${seconds % 60}s` : ""}`;
}
