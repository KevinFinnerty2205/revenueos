"use client";

import type { CallOutcome, Interaction } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatInteractionDate } from "@/lib/interactions";
import { BetaFeatureGate } from "@/components/beta-feature-gate";
import { PreInteractionBrief } from "@/components/pre-interaction-brief";
import { PostInteractionCapture } from "@/components/post-interaction-capture";
import { VisualEvidenceCapture } from "@/components/visual-evidence-capture";
import { RecordingFoundation } from "@/components/recording-foundation";
import { ImportedCallRecording } from "@/components/imported-call-recording";
import { OnlineMeetingCapture } from "@/components/online-meeting-capture";

export function InteractionDetail({
  interactionId,
}: {
  interactionId: string;
}) {
  const [interaction, setInteraction] = useState<Interaction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<Interaction>(`/api/v1/interactions/${interactionId}`, {
      signal: controller.signal,
    })
      .then(setInteraction)
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
            : "The interaction could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [interactionId]);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      setInteraction(
        await apiRequest<Interaction>(
          `/api/v1/interactions/${interactionId}/start`,
          { method: "POST", body: "{}" },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The interaction could not be started.",
      );
    } finally {
      setStarting(false);
    }
  }

  async function complete(callOutcome?: CallOutcome) {
    setCompleting(true);
    setError(null);
    try {
      setInteraction(
        await apiRequest<Interaction>(
          `/api/v1/interactions/${interactionId}/complete`,
          {
            method: "POST",
            body: JSON.stringify(callOutcome ? { callOutcome } : {}),
          },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The interaction could not be completed.",
      );
    } finally {
      setCompleting(false);
    }
  }

  if (loading) {
    return <p role="status">Loading interaction…</p>;
  }
  if (!interaction) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900"
      >
        {error ?? "The interaction was not found."}
      </div>
    );
  }

  const canComplete =
    interaction.lifecycleStatus === "planned" ||
    interaction.lifecycleStatus === "in_progress";
  return (
    <section aria-labelledby="interaction-detail-title">
      <Link
        className="text-sm font-bold text-teal-800 hover:underline"
        href="/interactions"
      >
        Back to interactions
      </Link>
      <div className="mt-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wide">
          <span className="rounded-full bg-teal-50 px-3 py-1 text-teal-800">
            {humanise(interaction.interactionType)}
          </span>
          <span
            role="status"
            aria-label="Interaction lifecycle status"
            className="rounded-full bg-slate-100 px-3 py-1 text-slate-700"
          >
            {humanise(interaction.lifecycleStatus)}
          </span>
        </div>
        <h1
          id="interaction-detail-title"
          className="mt-5 text-4xl font-semibold text-slate-950"
        >
          {interaction.title}
        </h1>
        <dl className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Scheduled
            </dt>
            <dd className="mt-1 text-slate-800">
              {formatInteractionDate(interaction.scheduledStartAt)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Completed
            </dt>
            <dd className="mt-1 text-slate-800">
              {formatInteractionDate(interaction.actualEndAt)}
            </dd>
          </div>
          {interaction.interactionType === "phone_call" ? (
            <>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  Direction
                </dt>
                <dd className="mt-1 text-slate-800">
                  {humanise(interaction.callDirection ?? "unknown")}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  Outcome · duration
                </dt>
                <dd className="mt-1 text-slate-800">
                  {interaction.callOutcome
                    ? humanise(interaction.callOutcome)
                    : "Not set"}
                  {interaction.durationSeconds !== null
                    ? ` · ${formatDuration(interaction.durationSeconds)}`
                    : ""}
                </dd>
              </div>
            </>
          ) : null}
          {interaction.interactionType === "online_meeting" ? (
            <>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  Platform
                </dt>
                <dd className="mt-1 text-slate-800">
                  {humanise(interaction.meetingPlatform ?? "other")}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  Capture
                </dt>
                <dd className="mt-1 text-slate-800">
                  {interaction.captureSource
                    ? humanise(interaction.captureSource)
                    : "Choose after meeting"}
                  {interaction.ingestionState
                    ? ` · ${humanise(interaction.ingestionState)}`
                    : ""}
                </dd>
              </div>
            </>
          ) : null}
        </dl>
        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-xl bg-red-50 p-4 text-sm text-red-900"
          >
            {error}
          </p>
        ) : null}
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            className="primary-button"
            href={`/interactions/${interaction.id}/companion`}
          >
            Open mobile Companion
          </Link>
          {interaction.interactionType === "phone_call" &&
          interaction.lifecycleStatus === "planned" ? (
            <button
              type="button"
              className="primary-button"
              disabled={starting || completing}
              onClick={() => void start()}
            >
              {starting ? "Starting…" : "Start call"}
            </button>
          ) : null}
          {interaction.interactionType === "online_meeting" &&
          interaction.lifecycleStatus === "planned" ? (
            <button
              type="button"
              className="primary-button"
              disabled={starting || completing}
              onClick={() => void start()}
            >
              {starting ? "Starting…" : "Start meeting"}
            </button>
          ) : null}
          {canComplete &&
          interaction.interactionType !== "phone_call" &&
          (interaction.interactionType !== "online_meeting" ||
            interaction.lifecycleStatus === "in_progress") ? (
            <button
              type="button"
              className="primary-button"
              disabled={completing}
              onClick={() => void complete()}
            >
              {completing
                ? "Completing…"
                : interaction.interactionType === "online_meeting"
                  ? "End meeting"
                  : "Complete interaction"}
            </button>
          ) : null}
          {canComplete && interaction.interactionType === "phone_call" ? (
            <>
              {interaction.lifecycleStatus === "in_progress" ? (
                <button
                  type="button"
                  className="primary-button"
                  disabled={completing}
                  onClick={() => void complete("connected")}
                >
                  {completing ? "Ending…" : "End connected call"}
                </button>
              ) : null}
              <button
                type="button"
                className="secondary-button"
                disabled={completing}
                onClick={() => void complete("no_answer")}
              >
                No answer
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={completing}
                onClick={() => void complete("voicemail")}
              >
                Left voicemail
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={completing}
                onClick={() => void complete("cancelled")}
              >
                Cancel call
              </button>
            </>
          ) : null}
          {interaction.meetingId ? (
            <Link
              className="secondary-button"
              href={`/meetings/${interaction.meetingId}`}
            >
              Open Meeting Intelligence
            </Link>
          ) : null}
          {interaction.interactionType === "online_meeting" &&
          interaction.meetingUrl ? (
            <a
              className="secondary-button"
              href={interaction.meetingUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open meeting
            </a>
          ) : null}
        </div>
      </div>
      <div className="mt-6" id="preparation">
        <BetaFeatureGate feature="aiCompanion">
          <PreInteractionBrief
            interactionId={interaction.id}
            interactionType={interaction.interactionType}
          />
        </BetaFeatureGate>
      </div>
      {interaction.lifecycleStatus === "completed" ? (
        <div className="mt-6" id="debrief">
          <BetaFeatureGate feature="aiDebrief">
            <PostInteractionCapture
              interactionId={interaction.id}
              interactionType={interaction.interactionType}
            />
          </BetaFeatureGate>
        </div>
      ) : null}
      <div className="mt-6" id="recording">
        {interaction.interactionType === "online_meeting" ? (
          interaction.lifecycleStatus === "completed" ? (
            <OnlineMeetingCapture interaction={interaction} />
          ) : (
            <section
              className="form-card"
              aria-labelledby="online-capture-boundary"
            >
              <h2 id="online-capture-boundary" className="form-legend">
                Use your meeting platform
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                RevenueOS remains passive while the meeting runs. It does not
                join, record system audio, monitor the browser or run a meeting
                bot. End the meeting here, then choose an authorised recording,
                transcript, AI Debrief or Voice Journal capture path.
              </p>
            </section>
          )
        ) : interaction.interactionType === "phone_call" ? (
          interaction.lifecycleStatus === "completed" ? (
            <BetaFeatureGate feature="recordingCapture">
              <ImportedCallRecording interactionId={interaction.id} />
            </BetaFeatureGate>
          ) : (
            <section
              className="form-card"
              aria-labelledby="phone-capture-boundary"
            >
              <h2 id="phone-capture-boundary" className="form-legend">
                Use your normal phone
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                RevenueOS does not intercept cellular calls, read device call
                logs, activate the microphone in the background or record this
                call. Complete it in your existing phone system, then capture
                the outcome while it is fresh.
              </p>
            </section>
          )
        ) : (
          <BetaFeatureGate feature="recordingCapture">
            <RecordingFoundation
              interactionId={interaction.id}
              interactionType={interaction.interactionType}
              lifecycleStatus={interaction.lifecycleStatus}
            />
          </BetaFeatureGate>
        )}
      </div>
      {interaction.interactionType !== "phone_call" ? (
        <div className="mt-6" id="visual-evidence">
          <BetaFeatureGate feature="visualEvidence">
            <VisualEvidenceCapture
              interactionId={interaction.id}
              interactionType={interaction.interactionType}
              lifecycleStatus={interaction.lifecycleStatus}
            />
          </BetaFeatureGate>
        </div>
      ) : null}
    </section>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}
