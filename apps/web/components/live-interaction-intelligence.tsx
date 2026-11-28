"use client";

import type {
  LiveIntelligenceResponse,
  ProvisionalLiveSignal,
} from "@revenueos/shared";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { ApiClientError, apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { decodeLiveIntelligenceResponse } from "@/lib/live-intelligence-response-identity";

function requestKey(prefix: string): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? `${prefix}-${crypto.randomUUID()}`
    : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function signalLabel(signal: ProvisionalLiveSignal): string {
  if (signal.signalType === "action_item") return "Possible action";
  if (signal.signalType === "security_legal")
    return "Possible security or legal concern";
  return `Possible ${humanise(signal.signalType).toLowerCase()}`;
}

function sentenceCase(value: string): string {
  const words = humanise(value).toLowerCase();
  return `${words.slice(0, 1).toUpperCase()}${words.slice(1)}`;
}

interface LiveInteractionIntelligenceProps {
  interactionId: string;
  organisationId: string;
  interactionInProgress?: boolean;
  interactionCompleted?: boolean;
}

interface LiveCommand {
  endpoint: string;
  body: string;
  failure: string;
  kind?: "reconcile";
  accepts: (response: LiveIntelligenceResponse) => boolean;
  expand?: boolean;
}

interface LiveAlert {
  message: string;
  reload?: true;
}

function canProcess(live: LiveIntelligenceResponse | null): boolean {
  return live?.state === "active" || live?.state === "processing";
}

function safeError(reason: unknown, fallback: string): string {
  return reason instanceof ApiClientError ? reason.message : fallback;
}

export function LiveInteractionIntelligence(
  props: LiveInteractionIntelligenceProps,
) {
  return (
    <LiveInteractionIntelligenceSession
      key={JSON.stringify([props.organisationId, props.interactionId])}
      {...props}
    />
  );
}

function LiveInteractionIntelligenceSession({
  interactionId,
  organisationId,
  interactionInProgress = false,
  interactionCompleted = false,
}: LiveInteractionIntelligenceProps) {
  const [live, setLive] = useState<LiveIntelligenceResponse | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<LiveAlert | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const latestLive = useRef<LiveIntelligenceResponse | null>(null);
  const sessionActive = useRef(false);
  const requestEpoch = useRef(0);
  const lifecycleEpoch = useRef(0);
  const commandPending = useRef(false);
  const processingRef = useRef(false);
  const basePath = `/api/v1/interactions/${encodeURIComponent(interactionId)}/live-intelligence`;

  const acceptLive = useCallback((response: LiveIntelligenceResponse) => {
    latestLive.current = response;
    setLive(response);
    setError(null);
  }, []);

  const isCurrent = useCallback(
    (epoch: number) => sessionActive.current && epoch === requestEpoch.current,
    [],
  );

  useLayoutEffect(() => {
    sessionActive.current = true;
    return () => {
      sessionActive.current = false;
      requestEpoch.current += 1;
    };
  }, []);

  useLayoutEffect(
    () => () => {
      lifecycleEpoch.current += 1;
    },
    [interactionCompleted, interactionInProgress],
  );

  useEffect(() => {
    const controller = new AbortController();
    const epoch = requestEpoch.current;
    const expectedSessionId = latestLive.current?.sessionId ?? undefined;
    const loadIsCurrent = () => !controller.signal.aborted && isCurrent(epoch);
    void apiRequest<unknown>(basePath, { signal: controller.signal })
      .then((payload) => {
        if (!loadIsCurrent()) return;
        acceptLive(
          decodeLiveIntelligenceResponse(payload, {
            interactionId,
            organisationId,
            sessionId: expectedSessionId,
          }),
        );
      })
      .catch((requestError: unknown) => {
        if (!loadIsCurrent()) return;
        setError({
          message: safeError(
            requestError,
            "Live Intelligence could not be loaded.",
          ),
          reload: true,
        });
      });
    return () => controller.abort();
  }, [
    acceptLive,
    basePath,
    interactionCompleted,
    interactionId,
    isCurrent,
    organisationId,
    retryKey,
  ]);

  const sessionId = canProcess(live) ? live?.sessionId : null;
  const nextPollSeconds = live?.nextPollSeconds;
  useEffect(() => {
    if (!interactionInProgress || !sessionId || nextPollSeconds === undefined)
      return;
    const phase = lifecycleEpoch.current;
    const interval = window.setInterval(() => {
      if (
        !sessionActive.current ||
        phase !== lifecycleEpoch.current ||
        commandPending.current ||
        processingRef.current ||
        !canProcess(latestLive.current) ||
        latestLive.current?.sessionId !== sessionId
      ) {
        return;
      }
      processingRef.current = true;
      const epoch = requestEpoch.current;
      const pollIsCurrent = () =>
        isCurrent(epoch) && phase === lifecycleEpoch.current;
      void apiRequest<unknown>(`${basePath}/process`, {
        method: "POST",
        body: JSON.stringify({ idempotencyKey: requestKey("live-poll") }),
      })
        .then((payload) => {
          if (!pollIsCurrent()) return;
          acceptLive(
            decodeLiveIntelligenceResponse(
              payload,
              { interactionId, organisationId, sessionId },
              "process",
            ),
          );
        })
        .catch((requestError: unknown) => {
          if (!pollIsCurrent()) return;
          setError({
            message: safeError(
              requestError,
              "The latest provisional update is unavailable.",
            ),
          });
        })
        .finally(() => {
          processingRef.current = false;
        });
    }, nextPollSeconds * 1_000);
    return () => window.clearInterval(interval);
  }, [
    acceptLive,
    basePath,
    interactionInProgress,
    interactionId,
    isCurrent,
    nextPollSeconds,
    organisationId,
    sessionId,
  ]);

  async function mutate(command: LiveCommand) {
    if (commandPending.current) return;
    commandPending.current = true;
    const epoch = ++requestEpoch.current;
    const phase = lifecycleEpoch.current;
    const commandIsCurrent = () =>
      isCurrent(epoch) && phase === lifecycleEpoch.current;
    const expectedSessionId = latestLive.current?.sessionId ?? undefined;
    setWorking(true);
    setError(null);
    try {
      const payload = await apiRequest<unknown>(
        `${basePath}/${command.endpoint}`,
        {
          method: "POST",
          body: command.body,
        },
      );
      if (!commandIsCurrent()) return;
      const response = decodeLiveIntelligenceResponse(
        payload,
        { interactionId, organisationId, sessionId: expectedSessionId },
        command.kind,
      );
      if (!command.accepts(response)) {
        setError({ message: command.failure });
        return;
      }
      acceptLive(response);
      if (command.expand) setExpanded(true);
    } catch (requestError: unknown) {
      if (commandIsCurrent()) {
        setError({ message: safeError(requestError, command.failure) });
      }
    } finally {
      commandPending.current = false;
      if (isCurrent(epoch)) setWorking(false);
    }
  }

  function start() {
    return mutate({
      endpoint: "start",
      body: JSON.stringify({ externalProcessingAcknowledged: false }),
      failure: "Live Intelligence could not be enabled.",
      accepts: canProcess,
      expand: true,
    });
  }

  function stop() {
    return mutate({
      endpoint: "stop",
      body: JSON.stringify({ reason: "user_disabled" }),
      failure: "Live Intelligence could not be stopped.",
      accepts: (response) => response.state === "completed",
    });
  }

  function dismiss(signal: ProvisionalLiveSignal) {
    return mutate({
      endpoint: `${encodeURIComponent(signal.id)}/dismiss`,
      body: JSON.stringify({ idempotencyKey: requestKey("live-dismiss") }),
      failure: "The provisional signal could not be dismissed.",
      accepts: (response) =>
        response.signals.every(
          (item) =>
            item.id !== signal.id || item.lifecycleStatus === "dismissed",
        ),
    });
  }

  function reconcile() {
    return mutate({
      endpoint: "reconcile",
      body: "{}",
      failure: "Live-to-final reconciliation is not ready.",
      kind: "reconcile",
      accepts: (response) =>
        response.state === "completed" && response.reconciliation !== null,
    });
  }

  if (!live && !error) {
    return (
      <p className="text-sm text-slate-500">Checking Live Intelligence…</p>
    );
  }

  const retry = error?.reload ? (
    <button
      type="button"
      className="secondary-button mt-3 min-h-12"
      onClick={() => {
        setError(null);
        setRetryKey((current) => current + 1);
      }}
    >
      Try again
    </button>
  ) : null;

  if (!live) {
    return (
      <div className="rounded-xl bg-red-50 p-4 text-sm text-red-900">
        <p role="alert">{error?.message}</p>
        {retry}
      </div>
    );
  }

  const errorNotice = error ? (
    <div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-950">
      <p role="alert">{error.message}</p>
      {retry}
    </div>
  ) : null;

  if (["unavailable", "disabled"].includes(live.state)) {
    return (
      <section
        className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4"
        aria-labelledby="live-availability-title"
      >
        <h2
          id="live-availability-title"
          className="font-semibold text-slate-950"
        >
          Live Intelligence unavailable
        </h2>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          {live.safeMessage}
        </p>
        {errorNotice}
      </section>
    );
  }

  if (live.state === "available") {
    return (
      <section
        className="mt-5 rounded-2xl border border-brand-secondary/20 bg-brand-secondary/10 p-4"
        aria-labelledby="live-available-title"
      >
        <p className="text-xs font-bold uppercase tracking-wide text-brand-secondary">
          Optional
        </p>
        <h2
          id="live-available-title"
          className="mt-1 font-semibold text-slate-950"
        >
          Live Intelligence is available
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-700">
          It uses the authorised progressive source and shows only provisional,
          reviewable signals. It never updates Revenue Brain or acts for you.
        </p>
        {errorNotice}
        {interactionInProgress ? (
          <button
            type="button"
            className="secondary-button mt-4 min-h-12"
            disabled={working}
            onClick={() => void start()}
          >
            {working ? "Enabling…" : "Enable Live Intelligence"}
          </button>
        ) : (
          <p className="mt-3 text-sm font-semibold text-brand-primary">
            You can enable it after the interaction starts.
          </p>
        )}
      </section>
    );
  }

  const visibleSignals = live.signals.filter(
    (signal) =>
      !["dismissed", "superseded", "expired"].includes(signal.lifecycleStatus),
  );
  const suggestedQuestion =
    live.openQuestions.find(
      (question) => question.progressStatus === "unresolved",
    ) ?? null;

  return (
    <section
      className="mt-5 rounded-3xl border border-brand-secondary/20 bg-white p-5 shadow-sm"
      aria-labelledby="live-companion-title"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
            Provisional · needs review
          </p>
          <h2
            id="live-companion-title"
            className="mt-1 text-xl font-semibold text-slate-950"
          >
            Live Companion
          </h2>
        </div>
        <button
          type="button"
          className="rounded-lg px-3 py-2 text-sm font-bold text-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-focus"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Collapse" : "Show"}
        </button>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {live.safeMessage}
      </p>
      {errorNotice}

      {expanded ? (
        <div className="mt-5 space-y-6">
          {suggestedQuestion ? (
            <div className="rounded-2xl border border-brand-accent/40 bg-brand-accent/10 p-4">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-brand-primary">
                Suggested next question
              </p>
              <p className="mt-2 text-base font-semibold leading-6 text-slate-950">
                {suggestedQuestion.label}
              </p>
              <p className="mt-2 text-xs leading-5 text-slate-600">
                From your preparation. Consider it only if it fits the
                conversation; Oryntela will not interrupt or speak for you.
              </p>
            </div>
          ) : null}

          {live.objectives.length ? (
            <div>
              <h3 className="text-sm font-bold text-slate-950">Objectives</h3>
              <ul className="mt-2 space-y-2">
                {live.objectives.map((objective) => (
                  <li
                    key={`${objective.itemType}-${objective.itemIndex}`}
                    className="flex gap-2 text-sm text-slate-700"
                  >
                    <span aria-hidden="true">
                      {objective.progressStatus === "unresolved" ? "○" : "✓?"}
                    </span>
                    <span>
                      {objective.label} —{" "}
                      {sentenceCase(objective.progressStatus)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <h3 className="text-sm font-bold text-slate-950">Emerging</h3>
            {visibleSignals.length ? (
              <ul className="mt-3 space-y-3">
                {visibleSignals.map((signal) => (
                  <li
                    key={signal.id}
                    className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wide text-brand-secondary">
                          {signalLabel(signal)}
                          {signal.priority === "high" ? " · High priority" : ""}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-slate-800">
                          {signal.statement}
                        </p>
                        {signal.evidenceStrength === "speaker_uncertain" ? (
                          <p className="mt-2 text-xs text-amber-900">
                            Speaker identity is uncertain; treat this signal
                            conservatively.
                          </p>
                        ) : null}
                        {signal.resolutionStatus !== "pending" ? (
                          <p className="mt-2 text-xs font-semibold text-slate-600">
                            Final review: {humanise(signal.resolutionStatus)}
                          </p>
                        ) : null}
                      </div>
                      {live.state === "active" && interactionInProgress ? (
                        <button
                          type="button"
                          className="rounded-lg px-2 py-1 text-xs font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-focus"
                          aria-label={`Dismiss ${signalLabel(signal).toLowerCase()}`}
                          disabled={working}
                          onClick={() => void dismiss(signal)}
                        >
                          Dismiss
                        </button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-slate-500">
                No material provisional signal yet. Silence is a valid result.
              </p>
            )}
          </div>

          {live.openQuestions.length ? (
            <div>
              <h3 className="text-sm font-bold text-slate-950">
                Open questions
              </h3>
              <ul className="mt-2 space-y-2 text-sm text-slate-700">
                {live.openQuestions.map((question) => (
                  <li key={`${question.itemType}-${question.itemIndex}`}>
                    {question.label} — {sentenceCase(question.progressStatus)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {live.reconciliation ? (
            <div className="rounded-2xl bg-brand-secondary/10 p-4">
              <h3 className="font-semibold text-brand-primary">
                Live-to-final review
              </h3>
              <p className="mt-2 text-sm text-brand-primary">
                {live.reconciliation.confirmed} confirmed ·{" "}
                {live.reconciliation.revised} revised ·{" "}
                {live.reconciliation.unsupported} unsupported ·{" "}
                {live.reconciliation.unresolved} unresolved
              </p>
            </div>
          ) : interactionCompleted ? (
            <button
              type="button"
              className="secondary-button min-h-12"
              disabled={working}
              onClick={() => void reconcile()}
            >
              {working ? "Comparing…" : "Compare with final intelligence"}
            </button>
          ) : null}

          {live.state === "active" && interactionInProgress ? (
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-sm font-bold text-slate-700 underline focus:outline-none focus:ring-2 focus:ring-brand-focus"
              disabled={working}
              onClick={() => void stop()}
            >
              Disable for this interaction
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
