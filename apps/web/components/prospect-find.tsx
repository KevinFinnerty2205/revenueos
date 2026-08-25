"use client";

import type {
  ProspectAvailability,
  ProspectCompanyCandidate,
  ProspectCompanySearch,
  ProspectRecentResearch,
  ProspectResearchBrief,
  ProspectResearchStatus,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";

const statusLabels: Record<ProspectResearchStatus, string> = {
  pending: "Research queued",
  researching: "Researching company…",
  ready: "Research ready",
  partial: "Research incomplete",
  failed: "Couldn’t complete research",
};

export function ProspectFind() {
  const router = useRouter();
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const [availability, setAvailability] = useState<ProspectAvailability | null>(
    null,
  );
  const [recent, setRecent] = useState<ProspectRecentResearch | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProspectCompanySearch | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [startingCandidate, setStartingCandidate] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ProspectAvailability>("/api/v1/prospect/availability", {
      signal: controller.signal,
    })
      .then(async (nextAvailability) => {
        setAvailability(nextAvailability);
        if (nextAvailability.enabled) {
          setRecent(
            await apiRequest<ProspectRecentResearch>(
              "/api/v1/prospect/research",
              { signal: controller.signal },
            ),
          );
        }
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError("Find is temporarily unavailable. Please try again.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleaned = query.trim();
    if (cleaned.length < 2) {
      setError("Enter at least two characters.");
      return;
    }
    setSearching(true);
    setError(null);
    setResults(null);
    try {
      const nextResults = await apiRequest<ProspectCompanySearch>(
        `/api/v1/prospect/companies/search?q=${encodeURIComponent(cleaned)}`,
      );
      setResults(nextResults);
      window.requestAnimationFrame(() => resultsHeading.current?.focus());
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Company search could not be completed.",
      );
    } finally {
      setSearching(false);
    }
  }

  async function startResearch(candidate: ProspectCompanyCandidate) {
    setStartingCandidate(candidate.candidateId);
    setError(null);
    try {
      const brief = await apiRequest<ProspectResearchBrief>(
        "/api/v1/prospect/research",
        {
          method: "POST",
          body: JSON.stringify({
            candidateId: candidate.candidateId,
            idempotencyKey: `find:${crypto.randomUUID()}`,
          }),
        },
      );
      router.push(`/find/${brief.target.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Company research could not be started.",
      );
      setStartingCandidate(null);
    }
  }

  if (loading) {
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading Find…
      </p>
    );
  }

  if (!availability?.enabled) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="RevenueOS Prospect"
          title="Find companies"
          description="Find and research the companies you should sell to."
        />
        <section className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
          <h2 className="text-xl font-semibold text-slate-950">
            Prospect is not available in this workspace
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            {availability?.state === "temporarily_unavailable"
              ? "Company research is temporarily unavailable. Your existing Accounts remain available."
              : "Your organisation administrator manages access to Prospect. Your existing Accounts remain unchanged."}
          </p>
          <Link href="/companies" className="secondary-button mt-5">
            View Accounts
          </Link>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="RevenueOS Prospect"
        title="Find companies"
        description="Turn public business information into a concise, sourced account brief."
      />

      <section
        className="rounded-3xl border border-teal-100 bg-white p-5 shadow-sm sm:p-8"
        aria-labelledby="find-question"
      >
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
          Start with a company
        </p>
        <h2
          id="find-question"
          className="mt-2 text-2xl font-semibold tracking-tight text-slate-950"
        >
          Which company are you looking for?
        </h2>
        <form
          onSubmit={search}
          role="search"
          className="mt-6 flex flex-col gap-3 sm:flex-row"
        >
          <label htmlFor="company-search" className="sr-only">
            Search company name or website
          </label>
          <input
            id="company-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            minLength={2}
            maxLength={200}
            required
            placeholder="Search company name or website"
            className="min-h-12 flex-1 rounded-xl border border-slate-300 px-4 text-base outline-none transition focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
          />
          <button
            type="submit"
            className="primary-button min-h-12"
            disabled={searching}
          >
            {searching ? "Searching…" : "Search companies"}
          </button>
        </form>
        {error ? (
          <p role="alert" className="mt-4 text-sm font-medium text-rose-700">
            {error}
          </p>
        ) : null}
      </section>

      {results ? (
        <section aria-labelledby="company-results-title">
          <h2
            id="company-results-title"
            ref={resultsHeading}
            tabIndex={-1}
            className="text-xl font-semibold text-slate-950 outline-none"
          >
            {results.items.length === 0
              ? "No companies found"
              : "Choose the right company"}
          </h2>
          {results.ambiguous ? (
            <p className="mt-2 text-sm text-slate-600">
              More than one company matches. Check the domain and location
              before you research.
            </p>
          ) : null}
          {results.items.length === 0 ? (
            <p className="mt-3 rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
              Try the official company website or a more specific name.
            </p>
          ) : (
            <div className="mt-4 grid gap-3">
              {results.items.map((candidate) => (
                <article
                  key={candidate.candidateId}
                  className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <h3 className="text-lg font-semibold text-slate-950">
                      {candidate.name}
                    </h3>
                    <p className="mt-1 break-all text-sm font-medium text-teal-800">
                      {candidate.domain}
                    </p>
                    <p className="mt-2 text-sm text-slate-600">
                      {[candidate.location, candidate.industry]
                        .filter(Boolean)
                        .join(" · ") || "Public company profile"}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      {candidate.providerAttribution}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="primary-button shrink-0"
                    disabled={startingCandidate !== null}
                    onClick={() => void startResearch(candidate)}
                  >
                    {startingCandidate === candidate.candidateId
                      ? "Starting research…"
                      : "Research company"}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      <section aria-labelledby="recent-research-title">
        <h2
          id="recent-research-title"
          className="text-xl font-semibold text-slate-950"
        >
          Recent research
        </h2>
        {!recent || recent.items.length === 0 ? (
          <p className="mt-3 rounded-2xl border border-dashed border-slate-300 bg-white/60 p-6 text-sm text-slate-600">
            Companies you research will appear here.
          </p>
        ) : (
          <div className="mt-3 divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            {recent.items.map((item) => (
              <Link
                key={item.target.id}
                href={`/find/${item.target.id}`}
                className="flex min-h-16 items-center justify-between gap-4 px-5 py-4 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-teal-600"
              >
                <span>
                  <span className="block font-semibold text-slate-950">
                    {item.target.name}
                  </span>
                  <span className="mt-1 block text-sm text-slate-500">
                    {item.target.domain}
                  </span>
                </span>
                <span className="text-right text-xs font-bold text-teal-800">
                  {statusLabels[item.status]}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
