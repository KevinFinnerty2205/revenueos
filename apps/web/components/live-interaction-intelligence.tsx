"use client";

import type {
  LiveIntelligenceResponse,
  LiveProcessResponse,
  ProvisionalLiveSignal,
} from "@revenueos/shared";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

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

export function LiveInteractionIntelligence({
  interactionId,
  interactionInProgress = false,
  interactionCompleted = false,
}: {
  interactionId: string;
  interactionInProgress?: boolean;
  interactionCompleted?: boolean;
}) {
  const [live, setLive] = useState<LiveIntelligenceResponse | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const processingRef = useRef(false);

  const load = useCallback(async () => {
    return apiRequest<LiveIntelligenceResponse>(
      `/api/v1/interactions/${interactionId}/live-intelligence`,
    );
  }, [interactionId]);

  useEffect(() => {
    let cancelled = false;
    void load()
      .then((response) => {
        if (!cancelled) setLive(response);
      })
      .catch((requestError: unknown) => {
        if (cancelled) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Live Intelligence could not be loaded.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  useEffect(() => {
    if (!live || !["active", "processing"].includes(live.state)) return;
    const interval = window.setInterval(() => {
      if (processingRef.current) return;
      processingRef.current = true;
      void apiRequest<LiveProcessResponse>(
        `/api/v1/interactions/${interactionId}/live-intelligence/process`,
        {
          method: "POST",
          body: JSON.stringify({ idempotencyKey: requestKey("live-poll") }),
        },
      )
        .then((response) => {
          setLive(response);
          setError(null);
        })
        .catch((requestError: unknown) => {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "The latest provisional update is unavailable.",
          );
        })
        .finally(() => {
          processingRef.current = false;
        });
    }, live.nextPollSeconds * 1_000);
    return () => window.clearInterval(interval);
  }, [interactionId, live]);

  async function start() {
    setWorking(true);
    setError(null);
    try {
      const response = await apiRequest<LiveIntelligenceResponse>(
        `/api/v1/interactions/${interactionId}/live-intelligence/start`,
        {
          method: "POST",
          body: JSON.stringify({ externalProcessingAcknowledged: false }),
        },
      );
      setLive(response);
      setExpanded(true);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Live Intelligence could not be enabled.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function stop() {
    setWorking(true);
    setError(null);
    try {
      setLive(
        await apiRequest<LiveIntelligenceResponse>(
          `/api/v1/interactions/${interactionId}/live-intelligence/stop`,
          {
            method: "POST",
            body: JSON.stringify({ reason: "user_disabled" }),
          },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Live Intelligence could not be stopped.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function dismiss(signal: ProvisionalLiveSignal) {
    setWorking(true);
    setError(null);
    try {
      setLive(
        await apiRequest<LiveIntelligenceResponse>(
          `/api/v1/interactions/${interactionId}/live-intelligence/${signal.id}/dismiss`,
          {
            method: "POST",
            body: JSON.stringify({
              idempotencyKey: requestKey("live-dismiss"),
            }),
          },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The provisional signal could not be dismissed.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function reconcile() {
    setWorking(true);
    setError(null);
    try {
      setLive(
        await apiRequest<LiveIntelligenceResponse>(
          `/api/v1/interactions/${interactionId}/live-intelligence/reconcile`,
          { method: "POST", body: "{}" },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Live-to-final reconciliation is not ready.",
      );
    } finally {
      setWorking(false);
    }
  }

  if (!live && !error) {
    return (
      <p className="text-sm text-slate-500">Checking Live Intelligence…</p>
    );
  }

  if (!live) {
    return (
      <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-900">
        {error}
      </p>
    );
  }

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
      </section>
    );
  }

  if (live.state === "available") {
    return (
      <section
        className="mt-5 rounded-2xl border border-indigo-200 bg-indigo-50 p-4"
        aria-labelledby="live-available-title"
      >
        <p className="text-xs font-bold uppercase tracking-wide text-indigo-800">
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
          <p className="mt-3 text-sm font-semibold text-indigo-900">
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

  return (
    <section
      className="mt-5 rounded-3xl border border-indigo-200 bg-white p-5 shadow-sm"
      aria-labelledby="live-companion-title"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-800">
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
          className="rounded-lg px-3 py-2 text-sm font-bold text-indigo-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Collapse" : "Show"}
        </button>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {live.safeMessage}
      </p>
      {error ? (
        <p
          role="alert"
          className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-950"
        >
          {error}
        </p>
      ) : null}

      {expanded ? (
        <div className="mt-5 space-y-6">
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
                        <p className="text-xs font-bold uppercase tracking-wide text-indigo-800">
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
                      {live.state === "active" ? (
                        <button
                          type="button"
                          className="rounded-lg px-2 py-1 text-xs font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-600"
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
            <div className="rounded-2xl bg-teal-50 p-4">
              <h3 className="font-semibold text-teal-950">
                Live-to-final review
              </h3>
              <p className="mt-2 text-sm text-teal-900">
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

          {live.state === "active" ? (
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-sm font-bold text-slate-700 underline focus:outline-none focus:ring-2 focus:ring-indigo-600"
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
