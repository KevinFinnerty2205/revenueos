"use client";

import type {
  Company,
  EntityPage,
  Meeting,
  MeetingStatus,
  MeetingType,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import {
  formatMeetingDate,
  meetingStatuses,
  meetingTypes,
} from "@/lib/meetings";

export function MeetingList() {
  const [result, setResult] = useState<EntityPage<Meeting> | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [page, setPage] = useState(1);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [meetingStatus, setMeetingStatus] = useState<MeetingStatus | "">("");
  const [meetingType, setMeetingType] = useState<MeetingType | "">("");

  useEffect(() => {
    const controller = new AbortController();
    const parameters = new URLSearchParams({
      page: String(page),
      pageSize: "20",
      sortBy: "meeting_date",
      sortOrder: "desc",
    });
    if (search) parameters.set("search", search);
    if (meetingStatus) parameters.set("status", meetingStatus);
    if (meetingType) parameters.set("meetingType", meetingType);

    Promise.all([
      apiRequest<EntityPage<Meeting>>(
        `/api/v1/meetings?${parameters.toString()}`,
        { signal: controller.signal },
      ),
      apiRequest<EntityPage<Company>>("/api/v1/companies?pageSize=100", {
        signal: controller.signal,
      }),
    ])
      .then(([meetings, companyPage]) => {
        setResult(meetings);
        setCompanies(companyPage.items);
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
            : "Meetings could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [meetingStatus, meetingType, page, retryKey, search]);

  const companyNames = useMemo(
    () => new Map(companies.map((company) => [company.id, company.name])),
    [companies],
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    beginReload();
    setSearch(searchDraft.trim());
  }

  function beginReload() {
    setLoading(true);
    setError(null);
    setPage(1);
  }

  return (
    <section aria-labelledby="meetings-title">
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Conversations
          </p>
          <h1
            id="meetings-title"
            className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
          >
            Meetings
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            Keep deliberate meeting records, participants and supplied
            transcripts together.
          </p>
        </div>
        <Link className="primary-button" href="/meetings/new">
          Create meeting
        </Link>
      </header>

      <form
        role="search"
        onSubmit={submitSearch}
        className="mb-5 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-[minmax(0,1fr)_auto_auto_auto]"
      >
        <label className="sr-only" htmlFor="meeting-search">
          Search meetings
        </label>
        <input
          id="meeting-search"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="Search meetings"
          className="form-control"
        />
        <label className="sr-only" htmlFor="meeting-status-filter">
          Filter by status
        </label>
        <select
          id="meeting-status-filter"
          value={meetingStatus}
          onChange={(event) => {
            beginReload();
            setMeetingStatus(event.target.value as MeetingStatus | "");
          }}
          className="form-control"
        >
          <option value="">All statuses</option>
          {meetingStatuses.map((value) => (
            <option key={value} value={value}>
              {humanise(value)}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="meeting-type-filter">
          Filter by meeting type
        </label>
        <select
          id="meeting-type-filter"
          value={meetingType}
          onChange={(event) => {
            beginReload();
            setMeetingType(event.target.value as MeetingType | "");
          }}
          className="form-control"
        >
          <option value="">All types</option>
          {meetingTypes.map((value) => (
            <option key={value} value={value}>
              {humanise(value)}
            </option>
          ))}
        </select>
        <button type="submit" className="secondary-button">
          Search
        </button>
      </form>

      {loading ? <MeetingLoading /> : null}
      {!loading && error ? (
        <MeetingError
          message={error}
          onRetry={() => {
            beginReload();
            setRetryKey((value) => value + 1);
          }}
        />
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <h2 className="text-xl font-semibold text-slate-950">
            No meetings found
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">
            Create a deliberate meeting record or adjust the current search and
            filters.
          </p>
          <Link className="primary-button mt-5" href="/meetings/new">
            Create meeting
          </Link>
        </div>
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <>
          <MeetingRows meetings={result.items} companyNames={companyNames} />
          <nav
            aria-label="Meetings pagination"
            className="mt-5 flex items-center justify-between gap-4"
          >
            <p className="text-sm text-slate-600">
              Page {result.page} of {result.pages}
            </p>
            <div className="flex gap-2">
              <button
                className="secondary-button"
                type="button"
                disabled={result.page <= 1}
                onClick={() => {
                  setLoading(true);
                  setPage((value) => Math.max(1, value - 1));
                }}
              >
                Previous
              </button>
              <button
                className="secondary-button"
                type="button"
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

function MeetingRows({
  meetings,
  companyNames,
}: {
  meetings: Meeting[];
  companyNames: Map<string, string>;
}) {
  return (
    <>
      <div className="space-y-3 md:hidden">
        {meetings.map((meeting) => (
          <article
            key={meeting.id}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <Link
              href={`/meetings/${meeting.id}`}
              className="text-lg font-bold text-slate-950 hover:text-teal-800"
            >
              {meeting.title}
            </Link>
            <p className="mt-2 text-sm text-slate-600">
              {formatMeetingDate(meeting.meetingDate)}
            </p>
            <p className="mt-1 text-sm text-slate-600">
              {humanise(meeting.meetingType)} · {humanise(meeting.status)}
            </p>
            <p className="mt-1 text-sm text-slate-600">
              {meeting.companyId
                ? (companyNames.get(meeting.companyId) ?? "Linked company")
                : "No company"}
            </p>
            <Link
              href={`/meetings/${meeting.id}/edit`}
              className="mt-4 inline-flex text-sm font-bold text-teal-700 hover:text-teal-900"
            >
              Edit meeting
            </Link>
          </article>
        ))}
      </div>
      <div className="hidden overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm md:block">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                {["Meeting", "Date", "Company", "Type", "Status", "Action"].map(
                  (label) => (
                    <th
                      key={label}
                      scope="col"
                      className="px-5 py-4 font-bold last:text-right"
                    >
                      {label}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {meetings.map((meeting) => (
                <tr key={meeting.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4">
                    <Link
                      className="font-bold text-slate-950 hover:text-teal-800"
                      href={`/meetings/${meeting.id}`}
                    >
                      {meeting.title}
                    </Link>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-700">
                    {formatMeetingDate(meeting.meetingDate)}
                  </td>
                  <td className="px-5 py-4 text-slate-700">
                    {meeting.companyId
                      ? (companyNames.get(meeting.companyId) ??
                        "Linked company")
                      : "—"}
                  </td>
                  <td className="px-5 py-4 text-slate-700">
                    {humanise(meeting.meetingType)}
                  </td>
                  <td className="px-5 py-4 text-slate-700">
                    {humanise(meeting.status)}
                  </td>
                  <td className="px-5 py-4 text-right">
                    <Link
                      className="font-bold text-teal-700 hover:text-teal-900"
                      href={`/meetings/${meeting.id}/edit`}
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

function MeetingLoading() {
  return (
    <div
      role="status"
      className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
    >
      <p className="font-semibold text-slate-700">Loading meetings…</p>
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

function MeetingError({
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
      <h2 className="font-bold text-rose-950">Meetings could not be loaded</h2>
      <p className="mt-2 text-sm text-rose-800">{message}</p>
      <button
        type="button"
        className="mt-4 rounded-lg bg-rose-900 px-4 py-2 text-sm font-bold text-white"
        onClick={onRetry}
      >
        Retry
      </button>
    </div>
  );
}
