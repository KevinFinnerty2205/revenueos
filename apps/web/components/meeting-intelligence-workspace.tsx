"use client";

import type {
  ActionItemsContent,
  BuyingSignalsContent,
  DecisionsContent,
  ExecutiveSummaryContent,
  FollowUpEmailContent,
  FollowUpEmailTone,
  MeetingIntelligenceCapability,
  MeetingIntelligenceCapabilityName,
  MeetingIntelligenceCapabilityState,
  MeetingIntelligenceGenerationResponse,
  MeetingIntelligenceOverallState,
  MeetingIntelligenceResponse,
  OpenQuestionsContent,
  ObjectionsCompetitiveSignalsContent,
  RisksBlockersContent,
} from "@revenueos/shared";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";

const POLLING_INTERVAL_MS = 3_000;
const tones: FollowUpEmailTone[] = ["professional", "friendly", "executive"];

const capabilityEndpoints: Record<MeetingIntelligenceCapabilityName, string> = {
  executive_summary: "executive-summary",
  buying_signals: "buying-signals",
  objections_competitive_signals: "objections-competitive-signals",
  decisions: "decisions",
  action_items: "action-items",
  risks_blockers: "risks-blockers",
  open_questions: "open-questions",
  follow_up_email: "follow-up-email",
};

const overallLabels: Record<MeetingIntelligenceOverallState, string> = {
  unavailable: "Unavailable",
  not_started: "Not started",
  partially_generated: "Partially ready",
  queued: "Queued",
  processing: "Generating",
  completed: "Ready",
  completed_with_empty_results: "Ready — some sections are empty",
  partially_failed: "Partially ready",
  failed: "Generation failed",
};

export function MeetingIntelligenceWorkspace({
  meetingId,
}: {
  meetingId: string;
}) {
  const [workspace, setWorkspace] =
    useState<MeetingIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [capabilityBusy, setCapabilityBusy] =
    useState<MeetingIntelligenceCapabilityName | null>(null);
  const [tone, setTone] = useState<FollowUpEmailTone>("professional");
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const requestSequence = useRef(0);
  const operationInFlight = useRef(false);
  const actionController = useRef<AbortController | null>(null);
  const observedOverallState = useRef<MeetingIntelligenceOverallState | null>(
    null,
  );
  const pollingEvent = useRef<"started" | "continued" | null>(null);

  useEffect(() => {
    observedOverallState.current = null;
    pollingEvent.current = null;
  }, [meetingId]);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    async function load() {
      if (operationInFlight.current) {
        timer = setTimeout(() => void load(), POLLING_INTERVAL_MS);
        return;
      }
      operationInFlight.current = true;
      controller = new AbortController();
      const sequence = ++requestSequence.current;
      const requestPollingEvent = pollingEvent.current;
      const query = new URLSearchParams();
      if (observedOverallState.current) {
        query.set("previousOverallState", observedOverallState.current);
      }
      if (requestPollingEvent) {
        query.set("pollingEvent", requestPollingEvent);
        pollingEvent.current = "continued";
      }
      const queryString = query.size > 0 ? `?${query.toString()}` : "";
      try {
        let next = await apiRequest<MeetingIntelligenceResponse>(
          `/api/v1/meetings/${meetingId}/intelligence${queryString}`,
          { signal: controller.signal },
        );
        if (stopped || sequence !== requestSequence.current) return;

        if (shouldQueueFollowUpEmail(next)) {
          next = await apiRequest<MeetingIntelligenceGenerationResponse>(
            `/api/v1/meetings/${meetingId}/intelligence/generate`,
            { method: "POST", signal: controller.signal },
          );
        }
        if (stopped || sequence !== requestSequence.current) return;
        observedOverallState.current = next.overallState;
        setWorkspace(next);
        if (next.followUpEmail.tone) setTone(next.followUpEmail.tone);
        setError(null);
        setLoading(false);
        if (isActive(next)) {
          if (requestPollingEvent === null) pollingEvent.current = "started";
          timer = setTimeout(() => void load(), POLLING_INTERVAL_MS);
        } else {
          pollingEvent.current = null;
        }
      } catch (requestError: unknown) {
        if (stopped || controller.signal.aborted) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Meeting Intelligence could not be loaded.",
        );
        setLoading(false);
      } finally {
        if (sequence === requestSequence.current) {
          operationInFlight.current = false;
        }
      }
    }

    void load();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      controller?.abort();
      requestSequence.current += 1;
      operationInFlight.current = false;
    };
  }, [meetingId, refreshKey]);

  useEffect(
    () => () => {
      actionController.current?.abort();
    },
    [],
  );

  async function orchestrate() {
    if (operationInFlight.current || generating) return;
    operationInFlight.current = true;
    setGenerating(true);
    setError(null);
    setCopyStatus(null);
    const controller = new AbortController();
    actionController.current = controller;
    const sequence = ++requestSequence.current;
    try {
      const next = await apiRequest<MeetingIntelligenceGenerationResponse>(
        `/api/v1/meetings/${meetingId}/intelligence/generate`,
        { method: "POST", signal: controller.signal },
      );
      if (sequence !== requestSequence.current) return;
      setWorkspace(next);
      observedOverallState.current = next.overallState;
      pollingEvent.current = isActive(next) ? "started" : null;
      if (next.followUpEmail.tone) setTone(next.followUpEmail.tone);
      setRefreshKey((value) => value + 1);
    } catch (requestError: unknown) {
      if (controller.signal.aborted) return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Meeting Intelligence generation could not be requested.",
      );
    } finally {
      if (sequence === requestSequence.current) {
        operationInFlight.current = false;
        setGenerating(false);
      }
    }
  }

  async function requestCapability(name: MeetingIntelligenceCapabilityName) {
    if (operationInFlight.current || capabilityBusy) return;
    operationInFlight.current = true;
    setCapabilityBusy(name);
    setError(null);
    setCopyStatus(null);
    const controller = new AbortController();
    actionController.current = controller;
    const sequence = ++requestSequence.current;
    try {
      await apiRequest<unknown>(
        `/api/v1/meetings/${meetingId}/intelligence/${capabilityEndpoints[name]}`,
        {
          method: "POST",
          signal: controller.signal,
          ...(name === "follow_up_email"
            ? { body: JSON.stringify({ tone }) }
            : {}),
        },
      );
      if (sequence !== requestSequence.current) return;
      pollingEvent.current = "started";
      setRefreshKey((value) => value + 1);
    } catch (requestError: unknown) {
      if (controller.signal.aborted) return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : `${humanise(name)} generation could not be requested.`,
      );
    } finally {
      if (sequence === requestSequence.current) {
        operationInFlight.current = false;
        setCapabilityBusy(null);
      }
    }
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
        Loading Meeting Intelligence…
      </div>
    );
  }

  if (!workspace) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        <h2 className="form-legend text-rose-950">
          Meeting Intelligence could not be loaded
        </h2>
        <p className="mt-3 text-sm text-rose-900">
          {error ?? "The workspace is temporarily unavailable."}
        </p>
        <button
          type="button"
          className="mt-5 rounded-lg bg-rose-900 px-4 py-2 text-sm font-bold text-white"
          onClick={() => {
            setLoading(true);
            setError(null);
            setRefreshKey((value) => value + 1);
          }}
        >
          Try again
        </button>
      </div>
    );
  }

  const failedCount = workspace.progress.failed;

  return (
    <section aria-labelledby="meeting-intelligence-title" className="space-y-6">
      <header className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-950 p-6 text-white shadow-sm sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <h2
                id="meeting-intelligence-title"
                className="text-2xl font-semibold tracking-tight sm:text-3xl"
              >
                Meeting Intelligence
              </h2>
              <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-bold">
                {overallLabels[workspace.overallState]}
              </span>
            </div>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              Turn the current meeting transcript into a clear summary, buying
              signals, objections, competitive context, decisions, actions,
              risks, open questions and a customer-ready follow-up.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
              <p role="status" aria-live="polite" className="font-bold">
                {workspace.progress.summary}
              </p>
              {workspace.lastUpdatedAt ? (
                <p className="text-slate-400">
                  Last updated {formatMeetingDate(workspace.lastUpdatedAt)}
                </p>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="rounded-lg bg-white px-4 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={
                !workspace.generationAvailable ||
                workspace.retryAvailable ||
                generating
              }
              onClick={() => void orchestrate()}
            >
              {generating ? "Requesting…" : "Generate Meeting Intelligence"}
            </button>
            {workspace.retryAvailable ? (
              <button
                type="button"
                className="rounded-lg border border-white/30 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-white/10 disabled:opacity-50"
                disabled={generating}
                onClick={() => void orchestrate()}
              >
                {generating
                  ? "Requesting…"
                  : `Retry failed section${failedCount === 1 ? "" : "s"}`}
              </button>
            ) : null}
          </div>
        </div>
        {error ? (
          <p
            role="alert"
            className="mt-5 rounded-xl border border-rose-300/40 bg-rose-950/70 p-3 text-sm text-rose-100"
          >
            {error} Completed sections remain available below.
          </p>
        ) : null}
      </header>

      <CapabilitySection
        id="executive-summary"
        title="Executive Summary"
        capability={workspace.executiveSummary}
        busy={capabilityBusy === "executive_summary"}
        onRequest={() => void requestCapability("executive_summary")}
      >
        <ExecutiveSummaryView content={workspace.executiveSummary.content} />
      </CapabilitySection>

      <CapabilitySection
        id="buying-signals"
        title="Buying Signals & Deal Momentum"
        capability={workspace.buyingSignals}
        busy={capabilityBusy === "buying_signals"}
        notGeneratedMessage="Buying signals have not been analysed for this meeting."
        onRequest={() => void requestCapability("buying_signals")}
      >
        <BuyingSignalsView content={workspace.buyingSignals.content} />
      </CapabilitySection>

      <CapabilitySection
        id="objections-competitive-signals"
        title="Objections & Competitive Signals"
        capability={workspace.objectionsCompetitiveSignals}
        busy={capabilityBusy === "objections_competitive_signals"}
        notGeneratedMessage="Objections and competitive signals have not been analysed for this meeting."
        onRequest={() =>
          void requestCapability("objections_competitive_signals")
        }
      >
        <ObjectionsCompetitiveSignalsView
          content={workspace.objectionsCompetitiveSignals.content}
        />
      </CapabilitySection>

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <CapabilitySection
          id="decisions"
          title="Key Decisions"
          capability={workspace.decisions}
          busy={capabilityBusy === "decisions"}
          onRequest={() => void requestCapability("decisions")}
        >
          <DecisionsView content={workspace.decisions.content} />
        </CapabilitySection>
        <CapabilitySection
          id="action-items"
          title="Action Items"
          capability={workspace.actionItems}
          busy={capabilityBusy === "action_items"}
          onRequest={() => void requestCapability("action_items")}
        >
          <ActionItemsView content={workspace.actionItems.content} />
        </CapabilitySection>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <CapabilitySection
          id="risks-blockers"
          title="Risks & Blockers"
          capability={workspace.risksBlockers}
          busy={capabilityBusy === "risks_blockers"}
          onRequest={() => void requestCapability("risks_blockers")}
        >
          <RisksBlockersView content={workspace.risksBlockers.content} />
        </CapabilitySection>
        <CapabilitySection
          id="open-questions"
          title="Open Questions"
          capability={workspace.openQuestions}
          busy={capabilityBusy === "open_questions"}
          onRequest={() => void requestCapability("open_questions")}
        >
          <OpenQuestionsView content={workspace.openQuestions.content} />
        </CapabilitySection>
      </div>

      <CapabilitySection
        id="follow-up-email"
        title="Follow-up Email"
        capability={workspace.followUpEmail}
        busy={capabilityBusy === "follow_up_email"}
        onRequest={() => void requestCapability("follow_up_email")}
      >
        <FollowUpEmailView
          content={workspace.followUpEmail.content}
          tone={tone}
          busy={capabilityBusy === "follow_up_email"}
          copyStatus={copyStatus}
          onToneChange={setTone}
          onCopy={copyEmail}
          onRegenerate={() => void requestCapability("follow_up_email")}
        />
      </CapabilitySection>
    </section>
  );
}

function CapabilitySection({
  id,
  title,
  capability,
  busy,
  notGeneratedMessage,
  onRequest,
  children,
}: {
  id: string;
  title: string;
  capability: MeetingIntelligenceCapability<unknown>;
  busy: boolean;
  notGeneratedMessage?: string;
  onRequest: () => void;
  children: ReactNode;
}) {
  const active =
    capability.state === "queued" || capability.state === "processing";
  const requestAvailable =
    capability.generationAvailable &&
    capability.state !== "completed" &&
    !active;
  return (
    <article
      className={`form-card min-w-0 ${
        capability.state === "failed" || capability.state === "cancelled"
          ? "border-amber-200 bg-amber-50"
          : ""
      }`}
      aria-labelledby={`${id}-heading`}
      aria-busy={active}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
        <div className="flex flex-wrap items-center gap-3">
          <h3 id={`${id}-heading`} className="form-legend">
            {title}
          </h3>
          <StatusLabel
            state={capability.state}
            empty={capability.emptyResult}
          />
        </div>
        {capability.generatedAt ? (
          <p className="text-xs font-medium text-slate-500">
            Generated {formatMeetingDate(capability.generatedAt)}
          </p>
        ) : null}
      </div>

      {capability.state === "completed" ? children : null}
      {capability.state === "unavailable" ? (
        <StateMessage>
          {capability.message ?? "This section is unavailable."}
        </StateMessage>
      ) : null}
      {capability.state === "not_generated" ? (
        <StateMessage>
          {notGeneratedMessage ?? "This section has not been generated yet."}
        </StateMessage>
      ) : null}
      {capability.state === "queued" ? (
        <StateMessage role="status">This section is queued.</StateMessage>
      ) : null}
      {capability.state === "processing" ? (
        <StateMessage role="status">
          This section is being generated…
        </StateMessage>
      ) : null}
      {capability.state === "failed" || capability.state === "cancelled" ? (
        <p role="alert" className="mt-5 text-sm leading-6 text-amber-900">
          {capability.message ?? "This section could not be completed."}
        </p>
      ) : null}

      {requestAvailable ? (
        <button
          type="button"
          className="secondary-button mt-5"
          disabled={busy}
          onClick={onRequest}
        >
          {busy
            ? "Requesting…"
            : capability.state === "not_generated"
              ? `Generate ${title}`
              : `Retry ${title}`}
        </button>
      ) : null}
    </article>
  );
}

function StatusLabel({
  state,
  empty,
}: {
  state: MeetingIntelligenceCapabilityState;
  empty: boolean;
}) {
  const label =
    state === "completed" && empty ? "Ready — no results" : humanise(state);
  const classes =
    state === "completed"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : state === "failed" || state === "cancelled"
        ? "border-amber-300 bg-amber-100 text-amber-900"
        : state === "queued" || state === "processing"
          ? "border-sky-200 bg-sky-50 text-sky-800"
          : "border-slate-200 bg-slate-100 text-slate-700";
  return (
    <span
      className={`rounded-full border px-2.5 py-1 text-xs font-bold ${classes}`}
    >
      {label}
    </span>
  );
}

function StateMessage({
  role,
  children,
}: {
  role?: "status";
  children: ReactNode;
}) {
  return (
    <p role={role} className="mt-5 text-sm leading-6 text-slate-600">
      {children}
    </p>
  );
}

function ExecutiveSummaryView({
  content,
}: {
  content: ExecutiveSummaryContent | null;
}) {
  if (!content) return <MissingContent />;
  return (
    <div className="mt-5">
      <p className="max-w-4xl whitespace-pre-wrap text-base leading-7 text-slate-800">
        {content.executiveSummary}
      </p>
      <dl className="mt-6 grid gap-4 border-t border-slate-100 pt-5 sm:grid-cols-3">
        <Detail label="Meeting type">{humanise(content.meetingType)}</Detail>
        <Detail label="Sentiment">{humanise(content.sentiment)}</Detail>
        <Detail label="Confidence">
          {formatConfidence(content.confidence)}
        </Detail>
      </dl>
    </div>
  );
}

function BuyingSignalsView({
  content,
}: {
  content: BuyingSignalsContent | null;
}) {
  if (!content) return <MissingContent />;
  const insufficient = content.overallMomentum === "insufficient_evidence";
  return (
    <div className="mt-5">
      <dl className="grid gap-4 sm:grid-cols-2">
        <Detail label="Current meeting momentum">
          {humanise(content.overallMomentum)}
        </Detail>
        <Detail label="Assessment confidence">
          {formatConfidence(content.confidence)}
        </Detail>
      </dl>
      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-5">
        <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">
          Momentum summary
        </h4>
        <p className="mt-2 text-sm leading-6 text-slate-800">
          {content.momentumSummary}
        </p>
      </div>
      {insufficient ? null : content.signals.length === 0 ? (
        <EmptyResult>
          No transcript-supported buying signals were identified in this
          meeting.
        </EmptyResult>
      ) : (
        <ol className="mt-3 divide-y divide-slate-100">
          {content.signals.map((signal, index) => (
            <li
              key={`${index}-${signal.signalType}`}
              className="py-5 first:pt-3 last:pb-0"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="text-sm font-bold leading-6 text-slate-950">
                  {humanise(signal.signalType)}
                </p>
                <span
                  className={`rounded-full border px-2.5 py-1 text-xs font-bold ${signalPolarityClasses[signal.polarity]}`}
                >
                  {humanise(signal.polarity)} signal
                </span>
              </div>
              <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                <Detail label="Strength">{humanise(signal.strength)}</Detail>
                <Detail label="Confidence">
                  {formatConfidence(signal.confidence)}
                </Detail>
              </dl>
              <Evidence>{signal.evidence}</Evidence>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function ObjectionsCompetitiveSignalsView({
  content,
}: {
  content: ObjectionsCompetitiveSignalsContent | null;
}) {
  if (!content) return <MissingContent />;
  const empty =
    content.objections.length === 0 && content.competitors.length === 0;
  return (
    <div className="mt-5">
      <dl className="grid gap-4 sm:grid-cols-2">
        <Detail label="Current meeting objection pressure">
          {humanise(content.overallObjectionPressure)}
        </Detail>
      </dl>
      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-5">
        <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">
          Summary
        </h4>
        <p className="mt-2 text-sm leading-6 text-slate-800">
          {content.summary}
        </p>
      </div>
      {empty ? (
        content.summary ===
        "No objections or competitive signals were identified in this meeting." ? null : (
          <EmptyResult>
            No objections or competitive signals were identified in this
            meeting.
          </EmptyResult>
        )
      ) : (
        <div className="mt-6 grid gap-7 xl:grid-cols-2">
          <section aria-labelledby="meeting-objections-heading">
            <h4
              id="meeting-objections-heading"
              className="text-sm font-bold text-slate-950"
            >
              Objections
            </h4>
            {content.objections.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                No objections were identified.
              </p>
            ) : (
              <ol className="mt-2 divide-y divide-slate-100">
                {content.objections.map((item, index) => (
                  <li
                    key={`${index}-${item.objection}`}
                    className="py-5 first:pt-3 last:pb-0"
                  >
                    <p className="text-sm font-bold leading-6 text-slate-950">
                      {item.objection}
                    </p>
                    <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                      <Detail label="Category">
                        {humanise(item.category)}
                      </Detail>
                      <Detail label="Status">{humanise(item.status)}</Detail>
                      <Detail label="Strength">
                        {humanise(item.strength)}
                      </Detail>
                      {item.owner ? (
                        <Detail label="Owner">{item.owner}</Detail>
                      ) : null}
                      <Detail label="Confidence">
                        {formatConfidence(item.confidence)}
                      </Detail>
                    </dl>
                    <Evidence>{item.evidence}</Evidence>
                  </li>
                ))}
              </ol>
            )}
          </section>
          <section aria-labelledby="meeting-competitors-heading">
            <h4
              id="meeting-competitors-heading"
              className="text-sm font-bold text-slate-950"
            >
              Competitors
            </h4>
            {content.competitors.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                No competitors were identified.
              </p>
            ) : (
              <ol className="mt-2 divide-y divide-slate-100">
                {content.competitors.map((item, index) => (
                  <li
                    key={`${index}-${item.name}`}
                    className="py-5 first:pt-3 last:pb-0"
                  >
                    <p className="text-sm font-bold leading-6 text-slate-950">
                      {item.name}
                    </p>
                    <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                      <Detail label="Position">
                        {humanise(item.position)}
                      </Detail>
                      <Detail label="Confidence">
                        {formatConfidence(item.confidence)}
                      </Detail>
                    </dl>
                    <Evidence>{item.evidence}</Evidence>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

const signalPolarityClasses = {
  positive: "border-emerald-200 bg-emerald-50 text-emerald-800",
  neutral: "border-slate-200 bg-slate-100 text-slate-700",
  negative: "border-amber-300 bg-amber-100 text-amber-900",
} as const;

function DecisionsView({ content }: { content: DecisionsContent | null }) {
  if (!content) return <MissingContent />;
  if (content.decisions.length === 0)
    return (
      <EmptyResult>No decisions were identified in this meeting.</EmptyResult>
    );
  return (
    <ol className="mt-2 divide-y divide-slate-100">
      {content.decisions.map((item, index) => (
        <li
          key={`${index}-${item.decision}`}
          className="py-5 first:pt-3 last:pb-0"
        >
          <p className="text-sm font-bold leading-6 text-slate-950">
            {item.decision}
          </p>
          <dl className="mt-3 grid gap-3 sm:grid-cols-3">
            {item.owner ? <Detail label="Owner">{item.owner}</Detail> : null}
            <Detail label="Status">{humanise(item.status)}</Detail>
            <Detail label="Confidence">
              {formatConfidence(item.confidence)}
            </Detail>
          </dl>
          <Evidence>{item.evidence}</Evidence>
        </li>
      ))}
    </ol>
  );
}

function ActionItemsView({ content }: { content: ActionItemsContent | null }) {
  if (!content) return <MissingContent />;
  if (content.actionItems.length === 0)
    return (
      <EmptyResult>
        No action items were identified in this meeting.
      </EmptyResult>
    );
  return (
    <ol className="mt-2 divide-y divide-slate-100">
      {content.actionItems.map((item, index) => (
        <li key={`${index}-${item.task}`} className="py-5 first:pt-3 last:pb-0">
          <p className="text-sm font-bold leading-6 text-slate-950">
            {item.task}
          </p>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {item.owner ? <Detail label="Owner">{item.owner}</Detail> : null}
            {item.dueDate ? (
              <Detail label="Due date">{formatDueDate(item.dueDate)}</Detail>
            ) : null}
            <Detail label="Priority">{humanise(item.priority)}</Detail>
            <Detail label="Status">{humanise(item.status)}</Detail>
            <Detail label="Confidence">
              {formatConfidence(item.confidence)}
            </Detail>
          </dl>
          <Evidence>{item.evidence}</Evidence>
        </li>
      ))}
    </ol>
  );
}

function RisksBlockersView({
  content,
}: {
  content: RisksBlockersContent | null;
}) {
  if (!content) return <MissingContent />;
  if (content.risks.length === 0)
    return (
      <EmptyResult>
        No risks or blockers were identified in this meeting.
      </EmptyResult>
    );
  return (
    <ol className="mt-2 divide-y divide-slate-100">
      {content.risks.map((item, index) => (
        <li key={`${index}-${item.risk}`} className="py-5 first:pt-3 last:pb-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <p className="text-sm font-bold leading-6 text-slate-950">
              {item.risk}
            </p>
            <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-800">
              {humanise(item.severity)} severity
            </span>
          </div>
          <dl className="mt-3 grid gap-3 sm:grid-cols-3">
            <Detail label="Category">{humanise(item.category)}</Detail>
            {item.owner ? <Detail label="Owner">{item.owner}</Detail> : null}
            <Detail label="Confidence">
              {formatConfidence(item.confidence)}
            </Detail>
          </dl>
          <Evidence>{item.evidence}</Evidence>
        </li>
      ))}
    </ol>
  );
}

function OpenQuestionsView({
  content,
}: {
  content: OpenQuestionsContent | null;
}) {
  if (!content) return <MissingContent />;
  if (content.openQuestions.length === 0)
    return (
      <EmptyResult>
        No open questions were identified in this meeting.
      </EmptyResult>
    );
  return (
    <ol className="mt-2 divide-y divide-slate-100">
      {content.openQuestions.map((item, index) => (
        <li
          key={`${index}-${item.question}`}
          className="py-5 first:pt-3 last:pb-0"
        >
          <p className="text-sm font-bold leading-6 text-slate-950">
            {item.question}
          </p>
          <dl className="mt-3 grid gap-3 sm:grid-cols-3">
            <Detail label="Importance">{humanise(item.importance)}</Detail>
            {item.owner ? <Detail label="Owner">{item.owner}</Detail> : null}
            <Detail label="Confidence">
              {formatConfidence(item.confidence)}
            </Detail>
          </dl>
          <Evidence>{item.evidence}</Evidence>
        </li>
      ))}
    </ol>
  );
}

function FollowUpEmailView({
  content,
  tone,
  busy,
  copyStatus,
  onToneChange,
  onCopy,
  onRegenerate,
}: {
  content: FollowUpEmailContent | null;
  tone: FollowUpEmailTone;
  busy: boolean;
  copyStatus: string | null;
  onToneChange: (tone: FollowUpEmailTone) => void;
  onCopy: (content: FollowUpEmailContent) => Promise<void>;
  onRegenerate: () => void;
}) {
  if (!content) return <MissingContent />;
  return (
    <div className="mt-5">
      <p className="text-xs font-medium text-slate-500">
        {humanise(content.tone)} tone · {formatConfidence(content.confidence)}{" "}
        confidence
      </p>
      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm leading-6 text-slate-800 sm:p-6">
        <p>
          <span className="font-bold text-slate-950">Subject: </span>
          {content.subject}
        </p>
        <p className="mt-5">{content.greeting}</p>
        <p className="mt-4 whitespace-pre-wrap">{content.summary}</p>
        <EmailList title="Decisions" items={content.decisions} />
        <EmailList title="Action Items" items={content.actionItems} />
        <EmailList title="Open Questions" items={content.openQuestions} />
        <p className="mt-5 whitespace-pre-wrap">{content.closing}</p>
      </div>
      {copyStatus ? (
        <p role="status" className="mt-4 text-sm text-slate-700">
          {copyStatus}
        </p>
      ) : null}
      <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <label className="text-sm font-bold text-slate-800">
          Tone
          <select
            className="form-control mt-2 block min-w-44"
            value={tone}
            onChange={(event) =>
              onToneChange(event.target.value as FollowUpEmailTone)
            }
          >
            {tones.map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="secondary-button"
            onClick={() => void onCopy(content)}
          >
            Copy
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={busy}
            onClick={onRegenerate}
          >
            {busy ? "Requesting…" : "Regenerate"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-slate-800">{children}</dd>
    </div>
  );
}

function Evidence({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 text-sm leading-6 text-slate-600">
      <span className="font-bold text-slate-700">Evidence: </span>
      {children}
    </p>
  );
}

function EmptyResult({ children }: { children: ReactNode }) {
  return <p className="mt-5 text-sm text-slate-700">{children}</p>;
}

function MissingContent() {
  return (
    <p role="alert" className="mt-5 text-sm text-rose-800">
      Completed content is unavailable. Try refreshing the workspace.
    </p>
  );
}

function EmailList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section className="mt-5" aria-label={title}>
      <h4 className="font-bold text-slate-950">{title}</h4>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {items.map((item, index) => (
          <li key={`${index}-${item}`}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function shouldQueueFollowUpEmail(workspace: MeetingIntelligenceResponse) {
  return (
    workspace.followUpEmail.state === "not_generated" &&
    workspace.followUpEmail.generationAvailable &&
    [
      workspace.executiveSummary,
      workspace.decisions,
      workspace.actionItems,
      workspace.openQuestions,
    ].every((capability) => capability.state === "completed")
  );
}

function isActive(workspace: MeetingIntelligenceResponse) {
  return workspace.progress.queued > 0 || workspace.progress.processing > 0;
}

function formatConfidence(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatDueDate(value: string) {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function renderFollowUpEmail(content: FollowUpEmailContent) {
  const sections = [
    `Subject: ${content.subject}`,
    content.greeting,
    content.summary,
    renderPlainTextList("Decisions", content.decisions),
    renderPlainTextList("Action Items", content.actionItems),
    renderPlainTextList("Open Questions", content.openQuestions),
    content.closing,
  ];
  return sections.filter((section) => section.length > 0).join("\n\n");
}

function renderPlainTextList(title: string, items: string[]) {
  if (items.length === 0) return "";
  return `${title}:\n${items.map((item) => `- ${item}`).join("\n")}`;
}
