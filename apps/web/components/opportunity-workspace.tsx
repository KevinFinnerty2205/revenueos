"use client";

import type {
  EntityPage,
  FollowUpEmailContent,
  Meeting,
  MeetingIntelligenceCapability,
  OpportunityMeetingSummary,
  OpportunityWorkspaceResponse,
} from "@revenueos/shared";
import Link from "next/link";
import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  ActionItemsView,
  BuyingSignalsView,
  DecisionsView,
  ExecutiveSummaryView,
  NextBestActionView,
  ObjectionsCompetitiveSignalsView,
  OpenQuestionsView,
  RisksBlockersView,
  StakeholderIntelligenceView,
} from "@/components/meeting-intelligence-workspace";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";

export function OpportunityWorkspace({
  opportunityId,
}: {
  opportunityId: string;
}) {
  const [workspace, setWorkspace] =
    useState<OpportunityWorkspaceResponse | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selectedMeetingId, setSelectedMeetingId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [associationError, setAssociationError] = useState<string | null>(null);
  const [associationMessage, setAssociationMessage] = useState<string | null>(
    null,
  );
  const [savingMeetingId, setSavingMeetingId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  const loadWorkspace = useCallback(
    async (signal: AbortSignal) => {
      const [loadedWorkspace, meetingPage] = await Promise.all([
        apiRequest<OpportunityWorkspaceResponse>(
          `/api/v1/opportunities/${opportunityId}/workspace`,
          { signal },
        ),
        apiRequest<EntityPage<Meeting>>(
          "/api/v1/meetings?pageSize=100&sortBy=meeting_date&sortOrder=desc",
          { signal },
        ),
      ]);
      return { workspace: loadedWorkspace, meetings: meetingPage.items };
    },
    [opportunityId],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadWorkspace(controller.signal)
      .then((loaded) => {
        setWorkspace(loaded.workspace);
        setMeetings(loaded.meetings);
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
            : "The opportunity workspace could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [loadWorkspace, refreshKey]);

  const availableMeetings = useMemo(
    () =>
      meetings.filter(
        (meeting) =>
          meeting.opportunityId === null ||
          meeting.opportunityId === opportunityId,
      ),
    [meetings, opportunityId],
  );

  async function updateAssociation(meeting: Meeting, nextId: string | null) {
    setSavingMeetingId(meeting.id);
    setAssociationError(null);
    setAssociationMessage(null);
    try {
      await apiRequest<Meeting>(`/api/v1/meetings/${meeting.id}/opportunity`, {
        method: "PATCH",
        body: JSON.stringify({
          opportunityId: nextId,
          expectedUpdatedAt: meeting.updatedAt,
        }),
      });
      setAssociationMessage(
        nextId
          ? "Meeting associated with this opportunity."
          : "Meeting removed from this opportunity.",
      );
      setSelectedMeetingId("");
      setLoading(true);
      setRefreshKey((value) => value + 1);
    } catch (requestError: unknown) {
      setAssociationError(
        requestError instanceof Error
          ? requestError.message
          : "The meeting association could not be saved.",
      );
    } finally {
      setSavingMeetingId(null);
    }
  }

  async function associateSelected() {
    const meeting = meetings.find((item) => item.id === selectedMeetingId);
    if (!meeting) {
      setAssociationError("Select a meeting to associate.");
      return;
    }
    await updateAssociation(meeting, opportunityId);
  }

  async function copyEmail(content: FollowUpEmailContent) {
    setCopyStatus(null);
    try {
      await navigator.clipboard.writeText(renderFollowUpEmail(content));
      setCopyStatus("Email copied to clipboard.");
    } catch {
      setCopyStatus(
        "The email could not be copied. Select the text and copy it manually.",
      );
    }
  }

  if (loading && !workspace) {
    return (
      <div role="status" className="form-card min-h-48">
        Loading opportunity workspace…
      </div>
    );
  }
  if (error || !workspace) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        <h1 className="text-xl font-bold text-rose-950">
          Opportunity workspace could not be loaded
        </h1>
        <p className="mt-2 text-sm text-rose-800">
          {error ?? "The opportunity was not found."}
        </p>
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
    );
  }

  const opportunity = workspace.opportunity;
  const intelligence = workspace.intelligence;
  const selectedMeeting = meetings.find(
    (meeting) => meeting.id === selectedMeetingId,
  );

  return (
    <section aria-labelledby="opportunity-title" className="space-y-6">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-teal-800">
                {humanise(opportunity.stage)}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
                {humanise(opportunity.status)}
              </span>
            </div>
            <h1
              id="opportunity-title"
              className="mt-4 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
            >
              {opportunity.name}
            </h1>
            <p className="mt-3 text-base text-slate-600">
              {opportunity.companyName ?? "No company"}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setLoading(true);
                setRefreshKey((value) => value + 1);
              }}
            >
              Refresh workspace
            </button>
            <Link
              href={`/opportunities/${opportunity.id}/edit`}
              className="primary-button"
            >
              Edit opportunity
            </Link>
          </div>
        </div>
        <dl className="mt-7 grid gap-5 border-t border-slate-100 pt-6 sm:grid-cols-2 lg:grid-cols-5">
          <HeaderDetail label="Value">
            {formatCurrency(opportunity.estimatedValue, opportunity.currency)}
          </HeaderDetail>
          <HeaderDetail label="Expected close">
            {formatDate(opportunity.expectedCloseDate)}
          </HeaderDetail>
          <HeaderDetail label="Owner">{opportunity.ownerName}</HeaderDetail>
          <HeaderDetail label="Last updated">
            {formatMeetingDate(opportunity.updatedAt)}
          </HeaderDetail>
          <HeaderDetail label="Latest meeting">
            {workspace.latestMeeting
              ? formatMeetingDate(workspace.latestMeeting.meetingDate)
              : "None associated"}
          </HeaderDetail>
        </dl>
        {opportunity.description ? (
          <p className="mt-6 max-w-4xl whitespace-pre-wrap text-sm leading-6 text-slate-700">
            {opportunity.description}
          </p>
        ) : null}
      </header>

      <AssociationPanel
        meetings={availableMeetings}
        selectedMeetingId={selectedMeetingId}
        saving={savingMeetingId !== null}
        error={associationError}
        message={associationMessage}
        onSelect={setSelectedMeetingId}
        onAssociate={() => void associateSelected()}
      />

      {!workspace.latestMeeting || !intelligence ? (
        <NoMeetingState />
      ) : (
        <>
          <section
            aria-labelledby="latest-next-best-action"
            className="overflow-hidden rounded-3xl border border-emerald-200 bg-white shadow-sm"
          >
            <div className="bg-slate-950 p-6 text-white sm:p-8">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-300">
                Latest associated meeting
              </p>
              <div className="mt-2 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h2
                    id="latest-next-best-action"
                    className="text-2xl font-semibold tracking-tight"
                  >
                    Latest Next Best Action
                  </h2>
                  <p className="mt-2 text-sm text-slate-300">
                    Based only on validated evidence from{" "}
                    {workspace.latestMeeting.title}.
                  </p>
                </div>
                <Link
                  href={`/meetings/${workspace.latestMeeting.id}`}
                  className="inline-flex min-h-11 items-center rounded-xl border border-white/30 px-4 text-sm font-bold text-white hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white"
                >
                  Open latest meeting intelligence
                </Link>
              </div>
            </div>
            <div className="p-6 sm:p-8">
              <CapabilityContent
                capability={intelligence.nextBestAction}
                unavailable="No Next Best Action has been generated for the latest associated meeting."
              >
                <NextBestActionView
                  content={intelligence.nextBestAction.content}
                />
              </CapabilityContent>
            </div>
          </section>

          {workspace.partialData ? (
            <p
              role="status"
              className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"
            >
              Some latest-meeting intelligence is not available. Completed,
              current information remains visible below.
            </p>
          ) : null}

          <WorkspaceSection
            id="latest-meeting-momentum"
            title="Latest Meeting Momentum & Buying Signals"
            capability={intelligence.buyingSignals}
          >
            <BuyingSignalsView content={intelligence.buyingSignals.content} />
          </WorkspaceSection>
          <WorkspaceSection
            id="objections"
            title="Objections & Competitive Signals"
            capability={intelligence.objectionsCompetitiveSignals}
          >
            <ObjectionsCompetitiveSignalsView
              content={intelligence.objectionsCompetitiveSignals.content}
            />
          </WorkspaceSection>
          <WorkspaceSection
            id="stakeholders"
            title="Latest Meeting Stakeholders"
            capability={intelligence.stakeholderIntelligence}
          >
            <StakeholderIntelligenceView
              content={intelligence.stakeholderIntelligence.content}
            />
          </WorkspaceSection>

          <div className="grid items-start gap-6 lg:grid-cols-2">
            <WorkspaceSection
              id="risks"
              title="Latest Meeting Risks & Blockers"
              capability={intelligence.risksBlockers}
            >
              <RisksBlockersView content={intelligence.risksBlockers.content} />
            </WorkspaceSection>
            <WorkspaceSection
              id="questions"
              title="Open Questions"
              capability={intelligence.openQuestions}
            >
              <OpenQuestionsView content={intelligence.openQuestions.content} />
            </WorkspaceSection>
            <WorkspaceSection
              id="actions"
              title="Action Items"
              capability={intelligence.actionItems}
            >
              <ActionItemsView content={intelligence.actionItems.content} />
            </WorkspaceSection>
            <WorkspaceSection
              id="decisions"
              title="Key Decisions"
              capability={intelligence.decisions}
            >
              <DecisionsView content={intelligence.decisions.content} />
            </WorkspaceSection>
          </div>

          <WorkspaceSection
            id="summary"
            title="Latest Executive Summary"
            capability={intelligence.executiveSummary}
          >
            <ExecutiveSummaryView
              content={intelligence.executiveSummary.content}
            />
          </WorkspaceSection>

          <WorkspaceSection
            id="follow-up-email"
            title="Latest Follow-up Email"
            capability={intelligence.followUpEmail}
          >
            <FollowUpEmailReadOnly
              content={intelligence.followUpEmail.content}
              copyStatus={copyStatus}
              onCopy={copyEmail}
            />
          </WorkspaceSection>
        </>
      )}

      <RecentMeetings
        meetings={workspace.recentMeetings}
        savingMeetingId={savingMeetingId}
        onDisassociate={(meeting) => {
          const source = meetings.find((item) => item.id === meeting.id);
          if (source) void updateAssociation(source, null);
        }}
      />
    </section>
  );
}

function WorkspaceSection<T>({
  id,
  title,
  capability,
  children,
}: {
  id: string;
  title: string;
  capability: MeetingIntelligenceCapability<T>;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={`${id}-title`} className="form-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 id={`${id}-title`} className="form-legend">
          {title}
        </h2>
        {capability.generatedAt ? (
          <p className="text-xs text-slate-500">
            Generated {formatMeetingDate(capability.generatedAt)}
          </p>
        ) : null}
      </div>
      <CapabilityContent capability={capability}>{children}</CapabilityContent>
    </section>
  );
}

function CapabilityContent<T>({
  capability,
  unavailable,
  children,
}: {
  capability: MeetingIntelligenceCapability<T>;
  unavailable?: string;
  children: ReactNode;
}) {
  if (capability.state === "completed" && capability.content) return children;
  return (
    <p className="mt-5 text-sm leading-6 text-slate-600">
      {unavailable ??
        capability.message ??
        safeCapabilityMessage(capability.state)}
    </p>
  );
}

function AssociationPanel({
  meetings,
  selectedMeetingId,
  saving,
  error,
  message,
  onSelect,
  onAssociate,
}: {
  meetings: Meeting[];
  selectedMeetingId: string;
  saving: boolean;
  error: string | null;
  message: string | null;
  onSelect: (value: string) => void;
  onAssociate: () => void;
}) {
  return (
    <section aria-labelledby="associate-meeting-title" className="form-card">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 id="associate-meeting-title" className="form-legend">
            Associate Meeting
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Choose an unassigned meeting from this organisation. Automatic
            matching is not used.
          </p>
        </div>
        <div className="flex w-full flex-col gap-3 sm:flex-row lg:max-w-2xl">
          <label className="sr-only" htmlFor="meeting-association">
            Meeting
          </label>
          <select
            id="meeting-association"
            className="form-control min-w-0 flex-1"
            value={selectedMeetingId}
            onChange={(event) => onSelect(event.target.value)}
          >
            <option value="">Select a meeting</option>
            {meetings.map((meeting) => (
              <option key={meeting.id} value={meeting.id}>
                {meeting.title} — {formatMeetingDate(meeting.meetingDate)}
                {meeting.opportunityId ? " (already associated)" : ""}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="primary-button"
            disabled={saving || !selectedMeetingId}
            onClick={onAssociate}
          >
            {saving ? "Saving…" : "Associate meeting"}
          </button>
        </div>
      </div>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="mt-4 text-sm text-emerald-800">
          {message}
        </p>
      ) : null}
    </section>
  );
}

function NoMeetingState() {
  return (
    <section
      className="form-card text-center"
      aria-labelledby="no-meetings-title"
    >
      <h2
        id="no-meetings-title"
        className="text-xl font-semibold text-slate-950"
      >
        No meetings associated
      </h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
        Associate a meeting above to see its current validated intelligence in
        this workspace. The opportunity metadata remains available without a
        meeting.
      </p>
    </section>
  );
}

function RecentMeetings({
  meetings,
  savingMeetingId,
  onDisassociate,
}: {
  meetings: OpportunityMeetingSummary[];
  savingMeetingId: string | null;
  onDisassociate: (meeting: OpportunityMeetingSummary) => void;
}) {
  return (
    <section aria-labelledby="recent-meetings-title" className="form-card">
      <h2 id="recent-meetings-title" className="form-legend">
        Recent Meetings
      </h2>
      {meetings.length === 0 ? (
        <p className="mt-4 text-sm text-slate-600">No meetings associated.</p>
      ) : (
        <ol className="mt-4 divide-y divide-slate-100">
          {meetings.map((meeting) => (
            <li
              key={meeting.id}
              className="flex flex-col gap-4 py-5 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <Link
                  href={`/meetings/${meeting.id}`}
                  className="font-bold text-teal-800 hover:text-teal-950 focus:outline-none focus:ring-2 focus:ring-teal-600"
                >
                  {meeting.title}
                </Link>
                <p className="mt-1 text-sm text-slate-600">
                  {formatMeetingDate(meeting.meetingDate)} ·{" "}
                  {meeting.participantCount} participant
                  {meeting.participantCount === 1 ? "" : "s"}
                </p>
                <p className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                  {meeting.transcriptAvailable
                    ? "Transcript supplied"
                    : "No transcript"}{" "}
                  · {readinessLabel(meeting)}
                </p>
              </div>
              <button
                type="button"
                className="secondary-button"
                disabled={savingMeetingId === meeting.id}
                onClick={() => onDisassociate(meeting)}
              >
                {savingMeetingId === meeting.id
                  ? "Removing…"
                  : "Remove association"}
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function FollowUpEmailReadOnly({
  content,
  copyStatus,
  onCopy,
}: {
  content: FollowUpEmailContent | null;
  copyStatus: string | null;
  onCopy: (content: FollowUpEmailContent) => Promise<void>;
}) {
  if (!content) return null;
  return (
    <div className="mt-5">
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm leading-6 text-slate-800 sm:p-6">
        <p>
          <span className="font-bold text-slate-950">Subject: </span>
          {content.subject}
        </p>
        <p className="mt-5">{content.greeting}</p>
        <p className="mt-4 whitespace-pre-wrap">{content.summary}</p>
        <EmailItems title="Decisions" items={content.decisions} />
        <EmailItems title="Action Items" items={content.actionItems} />
        <EmailItems title="Open Questions" items={content.openQuestions} />
        <p className="mt-5 whitespace-pre-wrap">{content.closing}</p>
      </div>
      <div className="mt-4 flex items-center justify-between gap-4">
        <p role="status" className="text-sm text-slate-600">
          {copyStatus}
        </p>
        <button
          type="button"
          className="secondary-button"
          onClick={() => void onCopy(content)}
        >
          Copy
        </button>
      </div>
    </div>
  );
}

function EmailItems({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-5">
      <p className="font-bold text-slate-950">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {items.map((item, index) => (
          <li key={`${index}-${item}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function HeaderDetail({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-slate-800">{children}</dd>
    </div>
  );
}

function safeCapabilityMessage(state: string) {
  if (state === "queued" || state === "processing") {
    return "This latest-meeting section is not ready yet.";
  }
  if (state === "failed" || state === "cancelled") {
    return "This latest-meeting section is currently unavailable.";
  }
  return "This section has not been generated for the latest associated meeting.";
}

function readinessLabel(meeting: OpportunityMeetingSummary) {
  if (meeting.intelligenceReadiness === "ready") return "Intelligence ready";
  if (meeting.intelligenceReadiness === "partial") {
    return `${meeting.intelligenceSectionsAvailable} of 10 sections ready`;
  }
  if (meeting.intelligenceReadiness === "unavailable") {
    return "Intelligence unavailable";
  }
  return "Intelligence not generated";
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

function renderFollowUpEmail(content: FollowUpEmailContent) {
  const lists = [
    ["Decisions", content.decisions],
    ["Action Items", content.actionItems],
    ["Open Questions", content.openQuestions],
  ] as const;
  return [
    `Subject: ${content.subject}`,
    "",
    content.greeting,
    "",
    content.summary,
    ...lists.flatMap(([title, items]) =>
      items.length
        ? ["", `${title}:`, ...items.map((item) => `- ${item}`)]
        : [],
    ),
    "",
    content.closing,
  ].join("\n");
}
