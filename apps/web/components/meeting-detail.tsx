"use client";

import type {
  Company,
  EntityPage,
  Meeting,
  MeetingAuditEvent,
  MeetingParticipant,
  Transcript,
} from "@revenueos/shared";
import Link from "next/link";
import {
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ApiClientError, apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";
import { ExecutiveSummaryPanel } from "@/components/executive-summary-panel";
import { DecisionsPanel } from "@/components/decisions-panel";
import { ActionItemsPanel } from "@/components/action-items-panel";
import { RisksBlockersPanel } from "@/components/risks-blockers-panel";
import { OpenQuestionsPanel } from "@/components/open-questions-panel";

type MeetingTab = "overview" | "intelligence" | "transcript" | "history";
const meetingTabs: MeetingTab[] = [
  "overview",
  "intelligence",
  "transcript",
  "history",
];

export function MeetingDetail({ meetingId }: { meetingId: string }) {
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [participants, setParticipants] = useState<MeetingParticipant[]>([]);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [history, setHistory] = useState<MeetingAuditEvent[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeTab, setActiveTab] = useState<MeetingTab>("overview");
  const [transcriptText, setTranscriptText] = useState("");
  const [language, setLanguage] = useState("en");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  const loadMeeting = useCallback(
    async (signal: AbortSignal) => {
      const [
        loadedMeeting,
        loadedParticipants,
        loadedTranscript,
        loadedHistory,
        companyPage,
      ] = await Promise.all([
        apiRequest<Meeting>(`/api/v1/meetings/${meetingId}`, { signal }),
        apiRequest<MeetingParticipant[]>(
          `/api/v1/meetings/${meetingId}/participants`,
          { signal },
        ),
        loadOptionalTranscript(meetingId, signal),
        apiRequest<MeetingAuditEvent[]>(
          `/api/v1/meetings/${meetingId}/history`,
          { signal },
        ),
        apiRequest<EntityPage<Company>>("/api/v1/companies?pageSize=100", {
          signal,
        }),
      ]);
      return {
        meeting: loadedMeeting,
        participants: loadedParticipants,
        transcript: loadedTranscript,
        history: loadedHistory,
        companies: companyPage.items,
      };
    },
    [meetingId],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadMeeting(controller.signal)
      .then((loaded) => {
        setMeeting(loaded.meeting);
        setParticipants(loaded.participants);
        setTranscript(loaded.transcript);
        setHistory(loaded.history);
        setCompanies(loaded.companies);
        setTranscriptText(loaded.transcript?.rawText ?? "");
        setLanguage(loaded.transcript?.language ?? "en");
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
            : "The meeting could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [loadMeeting, retryKey]);

  const companyName = useMemo(
    () =>
      meeting?.companyId
        ? (companies.find((company) => company.id === meeting.companyId)
            ?.name ?? "Linked company")
        : "No company",
    [companies, meeting],
  );

  async function saveTranscript() {
    setSaveError(null);
    setSavedMessage(null);
    if (!transcriptText.trim()) {
      setSaveError("Transcript text cannot be empty.");
      return;
    }
    setSaving(true);
    try {
      const saved = await apiRequest<Transcript>(
        `/api/v1/meetings/${meetingId}/transcript`,
        {
          method: transcript ? "PATCH" : "POST",
          body: JSON.stringify(
            transcript
              ? {
                  rawText: transcriptText.trim(),
                  language: language.trim(),
                  version: transcript.version,
                }
              : {
                  rawText: transcriptText.trim(),
                  language: language.trim(),
                  source: "manual",
                },
          ),
        },
      );
      setTranscript(saved);
      setTranscriptText(saved.rawText);
      setSavedMessage(`Transcript saved as version ${saved.version}.`);
      try {
        const refreshedHistory = await apiRequest<MeetingAuditEvent[]>(
          `/api/v1/meetings/${meetingId}/history`,
        );
        setHistory(refreshedHistory);
      } catch {
        setSavedMessage(
          `Transcript saved as version ${saved.version}. Refresh the page to reload audit history.`,
        );
      }
    } catch (requestError: unknown) {
      setSaveError(
        requestError instanceof Error
          ? requestError.message
          : "The transcript could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  function moveTabFocus(
    event: KeyboardEvent<HTMLButtonElement>,
    currentTab: MeetingTab,
  ) {
    const currentIndex = meetingTabs.indexOf(currentTab);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % meetingTabs.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + meetingTabs.length) % meetingTabs.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = meetingTabs.length - 1;
    }
    if (nextIndex === null) return;
    event.preventDefault();
    const nextTab = meetingTabs[nextIndex];
    setActiveTab(nextTab);
    document.getElementById(`meeting-tab-${nextTab}`)?.focus();
  }

  if (loading) {
    return (
      <div
        role="status"
        className="rounded-2xl border border-slate-200 bg-white p-8"
      >
        Loading meeting…
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-6"
      >
        <h1 className="text-xl font-bold text-rose-950">
          Meeting could not be loaded
        </h1>
        <p className="mt-2 text-sm text-rose-800">
          {error ?? "The meeting was not found."}
        </p>
        <button
          type="button"
          className="mt-4 rounded-lg bg-rose-900 px-4 py-2 text-sm font-bold text-white"
          onClick={() => {
            setLoading(true);
            setError(null);
            setRetryKey((value) => value + 1);
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <section aria-labelledby="meeting-detail-title">
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Link
            href="/meetings"
            className="text-sm font-bold text-teal-700 hover:text-teal-900"
          >
            ← Meetings
          </Link>
          <h1
            id="meeting-detail-title"
            className="mt-4 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
          >
            {meeting.title}
          </h1>
          <p className="mt-3 text-base text-slate-600">
            {formatMeetingDate(meeting.meetingDate)} ·{" "}
            {humanise(meeting.status)}
          </p>
        </div>
        <Link className="primary-button" href={`/meetings/${meeting.id}/edit`}>
          Edit meeting
        </Link>
      </header>

      <div
        role="tablist"
        aria-label="Meeting details"
        className="mb-5 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1"
      >
        {meetingTabs.map((tab) => (
          <button
            key={tab}
            id={`meeting-tab-${tab}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            aria-controls={`meeting-panel-${tab}`}
            tabIndex={activeTab === tab ? 0 : -1}
            className={`min-h-11 flex-1 rounded-lg px-4 text-sm font-bold transition ${
              activeTab === tab
                ? "bg-teal-700 text-white"
                : "text-slate-700 hover:bg-slate-50"
            }`}
            onClick={() => setActiveTab(tab)}
            onKeyDown={(event) => moveTabFocus(event, tab)}
          >
            {humanise(tab)}
          </button>
        ))}
      </div>

      {activeTab === "overview" ? (
        <div
          id="meeting-panel-overview"
          role="tabpanel"
          aria-labelledby="meeting-tab-overview"
          className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]"
        >
          <article className="form-card">
            <h2 className="form-legend">Overview</h2>
            <dl className="mt-5 grid gap-5 sm:grid-cols-2">
              <Detail label="Date">
                {formatMeetingDate(meeting.meetingDate)}
              </Detail>
              <Detail label="Company">{companyName}</Detail>
              <Detail label="Type">{humanise(meeting.meetingType)}</Detail>
              <Detail label="Status">{humanise(meeting.status)}</Detail>
              <Detail label="Description" fullWidth>
                {meeting.description ?? "No description"}
              </Detail>
            </dl>
          </article>
          <article className="form-card">
            <h2 className="form-legend">Participants</h2>
            {participants.length === 0 ? (
              <p className="mt-4 text-sm text-slate-600">
                No participants recorded.
              </p>
            ) : (
              <ul className="mt-4 divide-y divide-slate-100">
                {participants.map((participant) => (
                  <li key={participant.id} className="py-4 first:pt-0">
                    <p className="font-bold text-slate-900">
                      {participant.displayName ??
                        participant.email ??
                        "Linked contact"}
                    </p>
                    {participant.email ? (
                      <p className="mt-1 break-all text-sm text-slate-600">
                        {participant.email}
                      </p>
                    ) : null}
                    <p className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                      {humanise(participant.role)} ·{" "}
                      {humanise(participant.attendanceStatus)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </article>
        </div>
      ) : null}

      {activeTab === "transcript" ? (
        <div
          id="meeting-panel-transcript"
          role="tabpanel"
          aria-labelledby="meeting-tab-transcript"
          className="form-card"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="form-legend">Transcript</h2>
              <p className="mt-2 text-sm text-slate-600">
                Plain text only.{" "}
                {transcript
                  ? `Current version ${transcript.version}.`
                  : "No transcript has been supplied."}
              </p>
            </div>
            <label className="text-sm font-bold text-slate-800">
              Language
              <input
                className="form-control ml-3 w-28"
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
              />
            </label>
          </div>
          {saveError ? (
            <p
              id="transcript-save-error"
              role="alert"
              className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
            >
              {saveError}
            </p>
          ) : null}
          {savedMessage ? (
            <p
              role="status"
              className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"
            >
              {savedMessage}
            </p>
          ) : null}
          <label className="mt-5 block text-sm font-bold text-slate-800">
            Transcript text
            <textarea
              className="form-control mt-2 w-full font-mono leading-6"
              rows={20}
              maxLength={1_000_000}
              value={transcriptText}
              onChange={(event) => setTranscriptText(event.target.value)}
              placeholder="Paste authorised plain-text transcript content"
            />
          </label>
          <div className="mt-5 flex justify-end">
            <button
              type="button"
              disabled={saving}
              aria-describedby={saveError ? "transcript-save-error" : undefined}
              className="primary-button"
              onClick={saveTranscript}
            >
              {saving ? "Saving…" : "Save transcript"}
            </button>
          </div>
        </div>
      ) : null}

      {activeTab === "intelligence" ? (
        <div
          id="meeting-panel-intelligence"
          role="tabpanel"
          aria-labelledby="meeting-tab-intelligence"
        >
          <div className="grid gap-6">
            <ExecutiveSummaryPanel meetingId={meeting.id} />
            <DecisionsPanel meetingId={meeting.id} />
            <ActionItemsPanel meetingId={meeting.id} />
            <RisksBlockersPanel meetingId={meeting.id} />
            <OpenQuestionsPanel meetingId={meeting.id} />
          </div>
        </div>
      ) : null}

      {activeTab === "history" ? (
        <div
          id="meeting-panel-history"
          role="tabpanel"
          aria-labelledby="meeting-tab-history"
          className="form-card"
        >
          <h2 className="form-legend">Audit history</h2>
          <p className="mt-2 text-sm text-slate-600">
            Activity metadata only. Transcript and participant content is not
            copied into audit records.
          </p>
          {history.length === 0 ? (
            <p className="mt-5 text-sm text-slate-600">
              No audit activity recorded.
            </p>
          ) : (
            <ol className="mt-5 divide-y divide-slate-100">
              {history.map((event) => (
                <li
                  key={event.id}
                  className="grid gap-2 py-4 first:pt-0 sm:grid-cols-[10rem_minmax(0,1fr)]"
                >
                  <time
                    dateTime={event.createdAt}
                    className="text-sm text-slate-500"
                  >
                    {formatMeetingDate(event.createdAt)}
                  </time>
                  <div>
                    <p className="font-bold text-slate-900">
                      {humanise(event.entityType)}{" "}
                      {humanise(event.action).toLowerCase()}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      Fields:{" "}
                      {event.changedFields.map(humanise).join(", ") || "none"}
                      {event.version ? ` · Version ${event.version}` : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
    </section>
  );
}

function Detail({
  label,
  fullWidth = false,
  children,
}: {
  label: string;
  fullWidth?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={fullWidth ? "sm:col-span-2" : undefined}>
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-900">
        {children}
      </dd>
    </div>
  );
}

async function loadOptionalTranscript(
  meetingId: string,
  signal: AbortSignal,
): Promise<Transcript | null> {
  try {
    return await apiRequest<Transcript>(
      `/api/v1/meetings/${meetingId}/transcript`,
      { signal },
    );
  } catch (error) {
    if (error instanceof ApiClientError && error.status === 404) return null;
    throw error;
  }
}
