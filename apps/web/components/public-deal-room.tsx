"use client";

import type { PublicDealRoomResolveResponse } from "@revenueos/shared";
import { useEffect, useRef, useState } from "react";
import { BrandLogo } from "@/components/brand-logo";
import { apiBlob, apiRequest } from "@/lib/api";

const unavailableMessage = "This Deal Room is no longer available.";

function accessToken(): string | null {
  const hash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  return new URLSearchParams(hash).get("access");
}

function friendly(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/^./u, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null, withTime = false): string {
  if (!value) return "To be agreed";
  return new Intl.DateTimeFormat(
    "en-AU",
    withTime
      ? { dateStyle: "full", timeStyle: "short" }
      : { dateStyle: "medium" },
  ).format(new Date(value));
}

export function PublicDealRoom() {
  const [response, setResponse] =
    useState<PublicDealRoomResolveResponse | null>(null);
  const token = useRef<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    let controller: AbortController | null = null;
    const resolveCurrentToken = () => {
      const currentToken = accessToken();
      if (!currentToken && token.current) return;
      controller?.abort();
      controller = new AbortController();
      const requestController = controller;
      token.current = currentToken;
      setResponse(null);
      setUnavailable(false);
      setLoading(true);
      if (!currentToken) {
        setUnavailable(true);
        setLoading(false);
        return;
      }
      window.history.replaceState(
        window.history.state,
        "",
        `${window.location.pathname}${window.location.search}`,
      );
      apiRequest<PublicDealRoomResolveResponse>(
        "/api/v1/deal-rooms/public/resolve",
        {
          method: "POST",
          signal: requestController.signal,
          body: JSON.stringify({ token: currentToken }),
        },
      )
        .then((result) => {
          if (!requestController.signal.aborted) setResponse(result);
        })
        .catch((reason: unknown) => {
          if (requestController.signal.aborted) return;
          if (reason instanceof DOMException && reason.name === "AbortError")
            return;
          setUnavailable(true);
        })
        .finally(() => {
          if (!requestController.signal.aborted) setLoading(false);
        });
    };
    window.addEventListener("hashchange", resolveCurrentToken);
    void Promise.resolve().then(resolveCurrentToken);
    return () => {
      window.removeEventListener("hashchange", resolveCurrentToken);
      controller?.abort();
    };
  }, []);

  async function download(resourceId: string, title: string): Promise<void> {
    if (!token.current) return;
    setDownloading(resourceId);
    setDownloadError(null);
    try {
      const blob = await apiBlob(
        `/api/v1/deal-rooms/public/resources/${resourceId}/download`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: token.current }),
        },
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${title.replace(/[^A-Za-z0-9 ._-]/gu, "").slice(0, 100) || "Presentation"}.pptx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError("This resource is no longer available.");
    } finally {
      setDownloading(null);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-brand-background p-6">
        <div
          role="status"
          className="flex items-center gap-4 rounded-2xl bg-white px-6 py-5 text-sm font-semibold text-slate-700 shadow-sm"
        >
          <BrandLogo className="size-8" decorative variant="symbol" />
          <span>Opening your Deal Room…</span>
        </div>
      </main>
    );
  }

  if (unavailable || !response) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-brand-primary p-6 text-center">
        <section
          aria-labelledby="unavailable-title"
          className="w-full max-w-lg rounded-3xl bg-white p-8 shadow-2xl sm:p-12"
        >
          <BrandLogo className="mx-auto size-12" variant="symbol" />
          <h1
            id="unavailable-title"
            className="mt-6 text-2xl font-semibold tracking-tight text-slate-950"
          >
            {unavailableMessage}
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Ask your contact for a current secure link.
          </p>
        </section>
      </main>
    );
  }

  const room = response.room;
  const hasJourney = room.milestones.length > 0;
  const hasResources = room.resources.length > 0;
  const hasPeople = room.stakeholders.length > 0;

  return (
    <main className="deal-room-public min-h-screen bg-brand-background text-slate-950">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <span
              aria-hidden="true"
              className="flex size-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-700"
            >
              {room.sellerCompanyName.slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-slate-950">
                {room.sellerCompanyName}
              </p>
              <p className="text-xs text-slate-500">
                Secure customer Deal Room
              </p>
            </div>
          </div>
          <p className="hidden text-xs font-semibold text-slate-500 sm:block">
            Published {formatDate(room.publishedAt)}
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8 sm:py-12">
        <section
          aria-labelledby="deal-room-heading"
          className="overflow-hidden rounded-[2rem] bg-brand-primary px-6 py-10 text-white shadow-xl sm:px-10 sm:py-14 lg:px-14"
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-primary-foreground">
            {room.customerCompanyName ?? "Customer collaboration"}
          </p>
          <h1
            id="deal-room-heading"
            className="mt-4 max-w-4xl text-3xl font-semibold tracking-tight sm:text-5xl"
          >
            {room.opportunityName}
          </h1>
          <p className="mt-4 text-sm font-semibold text-brand-primary-foreground">
            Your deal with {room.sellerCompanyName}
          </p>
          {room.overview ? (
            <p className="mt-7 max-w-3xl whitespace-pre-wrap text-base leading-8 text-brand-primary-foreground sm:text-lg">
              {room.overview}
            </p>
          ) : null}
          <nav
            aria-label="Deal Room sections"
            className="mt-8 flex flex-wrap gap-2 text-sm font-bold"
          >
            {room.businessCase ? (
              <a
                className="rounded-full bg-white/10 px-4 py-2 hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-white"
                href="#business-case"
              >
                Business case
              </a>
            ) : null}
            {hasJourney ? (
              <a
                className="rounded-full bg-white/10 px-4 py-2 hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-white"
                href="#next-steps"
              >
                Next steps
              </a>
            ) : null}
            {hasResources ? (
              <a
                className="rounded-full bg-white/10 px-4 py-2 hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-white"
                href="#resources"
              >
                Resources
              </a>
            ) : null}
            {hasPeople ? (
              <a
                className="rounded-full bg-white/10 px-4 py-2 hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-white"
                href="#people"
              >
                People
              </a>
            ) : null}
          </nav>
        </section>

        <div className="mt-8 grid gap-8">
          {room.businessCase ? (
            <section
              id="business-case"
              aria-labelledby="business-case-title"
              className="scroll-mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9"
            >
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
                Business case
              </p>
              <h2
                id="business-case-title"
                className="mt-2 text-2xl font-semibold tracking-tight"
              >
                {room.businessCase.title}
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                Approved revision {room.businessCase.version} ·{" "}
                {room.businessCase.currency}
              </p>
              <div className="mt-6 grid gap-5 lg:grid-cols-3">
                {room.businessCase.scenarios.map((scenario) => (
                  <article
                    key={scenario.name}
                    className="rounded-2xl bg-slate-50 p-5"
                  >
                    <h3 className="font-bold text-slate-950">
                      {scenario.name}
                    </h3>
                    <dl className="mt-4 grid gap-4">
                      {scenario.outputs.map((output) => (
                        <div key={`${output.label}-${output.value}`}>
                          <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                            {output.label}
                          </dt>
                          <dd className="mt-1 text-xl font-semibold text-brand-primary">
                            {output.value}
                            {output.unit && !output.value.includes(output.unit)
                              ? ` ${output.unit}`
                              : ""}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {room.commercialSummary ? (
            <section
              aria-labelledby="commercial-title"
              className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9"
            >
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
                Agreed commercial context
              </p>
              <h2 id="commercial-title" className="sr-only">
                Commercial summary
              </h2>
              <p className="mt-3 max-w-4xl whitespace-pre-wrap text-base leading-7 text-slate-700">
                {room.commercialSummary}
              </p>
            </section>
          ) : null}

          {hasJourney ? (
            <section
              id="next-steps"
              aria-labelledby="next-steps-title"
              className="scroll-mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9"
            >
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
                Shared plan
              </p>
              <h2
                id="next-steps-title"
                className="mt-2 text-2xl font-semibold tracking-tight"
              >
                Next steps and timeline
              </h2>
              <ol className="mt-6 grid gap-4 md:grid-cols-2">
                {room.milestones.map((milestone, index) => (
                  <li
                    key={milestone.id}
                    className="rounded-2xl border border-slate-200 p-5"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-secondary/15 text-xs font-black text-brand-primary">
                        {index + 1}
                      </span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
                        {friendly(milestone.status)}
                      </span>
                    </div>
                    <h3 className="mt-4 text-base font-bold text-slate-950">
                      {milestone.title}
                    </h3>
                    <p className="mt-2 text-sm text-slate-600">
                      Owner: {friendly(milestone.ownerParty)} ·{" "}
                      {formatDate(milestone.targetDate)}
                    </p>
                    {milestone.note ? (
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                        {milestone.note}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          {hasResources ? (
            <section
              id="resources"
              aria-labelledby="resources-title"
              className="scroll-mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9"
            >
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
                Reviewed resources
              </p>
              <h2
                id="resources-title"
                className="mt-2 text-2xl font-semibold tracking-tight"
              >
                Documents and links
              </h2>
              {downloadError ? (
                <p
                  role="alert"
                  className="mt-4 rounded-xl bg-rose-50 p-4 text-sm font-semibold text-rose-900"
                >
                  {downloadError}
                </p>
              ) : null}
              <ul className="mt-6 grid gap-3 sm:grid-cols-2">
                {room.resources.map((resource) => (
                  <li
                    key={resource.id}
                    className="flex min-h-28 flex-col items-start justify-between gap-4 rounded-2xl bg-slate-50 p-5"
                  >
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                        {resource.kind === "presentation"
                          ? "Presentation"
                          : "External resource"}
                      </p>
                      <h3 className="mt-2 font-bold text-slate-950">
                        {resource.title}
                      </h3>
                    </div>
                    {resource.kind === "external_link" && resource.url ? (
                      <a
                        className="font-bold text-brand-secondary underline decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-focus"
                        href={resource.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        referrerPolicy="no-referrer"
                      >
                        Open resource{" "}
                        <span className="sr-only">: {resource.title}</span>
                      </a>
                    ) : null}
                    {resource.kind === "presentation" &&
                    resource.downloadAvailable ? (
                      <button
                        type="button"
                        className="font-bold text-brand-secondary underline decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-focus disabled:opacity-60"
                        disabled={downloading === resource.id}
                        onClick={() =>
                          void download(resource.id, resource.title)
                        }
                      >
                        {downloading === resource.id
                          ? "Preparing download…"
                          : "Download presentation"}
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {hasPeople ? (
            <section
              id="people"
              aria-labelledby="people-title"
              className="scroll-mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9"
            >
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
                People
              </p>
              <h2
                id="people-title"
                className="mt-2 text-2xl font-semibold tracking-tight"
              >
                Working together
              </h2>
              <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {room.stakeholders.map((person) => (
                  <li key={person.id} className="rounded-2xl bg-slate-50 p-5">
                    <p className="font-bold text-slate-950">{person.name}</p>
                    <p className="mt-1 text-sm text-slate-600">{person.role}</p>
                    <p className="mt-3 text-xs font-bold uppercase tracking-wide text-brand-secondary">
                      {person.company} ·{" "}
                      {person.party === "seller" ? "Our team" : "Customer"}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {room.nextMeetingAt ? (
            <section
              aria-labelledby="next-meeting-title"
              className="rounded-3xl bg-amber-100 p-6 text-amber-950 sm:p-9"
            >
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-800">
                Next meeting or decision
              </p>
              <h2
                id="next-meeting-title"
                className="mt-2 text-xl font-semibold"
              >
                {formatDate(room.nextMeetingAt, true)}
              </h2>
            </section>
          ) : null}
        </div>

        <footer className="mt-10 border-t border-slate-200 py-6 text-xs leading-5 text-slate-500">
          <p>
            Shared securely by {room.sellerCompanyName}. Read-only · Revision{" "}
            {room.revision}
            {response.expiresAt
              ? ` · Access expires ${formatDate(response.expiresAt, true)}`
              : ""}
          </p>
          <div className="mt-4 flex items-center gap-2">
            <BrandLogo className="size-5" decorative variant="symbol" />
            <span>Powered by Oryntela</span>
          </div>
        </footer>
      </div>
    </main>
  );
}
