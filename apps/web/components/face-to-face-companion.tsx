"use client";

import type {
  Interaction,
  InteractionMarker,
  InteractionMarkerType,
  PreInteractionBriefRequestResponse,
  PreInteractionBriefResponse,
  RecordingSession,
  VisualEvidence,
} from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { PostInteractionCapture } from "@/components/post-interaction-capture";
import { OnlineMeetingCapture } from "@/components/online-meeting-capture";
import {
  RecordingFoundation,
  type RecordingActivity,
} from "@/components/recording-foundation";
import { VisualEvidenceCapture } from "@/components/visual-evidence-capture";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatInteractionDate } from "@/lib/interactions";

type CaptureChoice = "undecided" | "recording" | "passive";

interface Capabilities {
  featureFlags: Record<string, boolean>;
}

const MARKERS: Array<{
  type: InteractionMarkerType;
  label: string;
}> = [
  { type: "important_moment", label: "Important" },
  { type: "customer_question", label: "Question" },
  { type: "buying_signal", label: "Buying signal" },
  { type: "objection", label: "Objection" },
  { type: "decision", label: "Decision" },
  { type: "action_item", label: "Action" },
  { type: "risk", label: "Risk" },
  { type: "follow_up", label: "Follow-up" },
  { type: "requested_material", label: "Material requested" },
  { type: "strong_engagement", label: "Strong engagement" },
  { type: "stakeholder", label: "Stakeholder" },
  { type: "timeline", label: "Timeline" },
];

function requestKey(prefix: string): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? `${prefix}-${crypto.randomUUID()}`
    : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function captureStorageKey(interactionId: string): string {
  return `revenueos:companion:capture-choice:${interactionId}`;
}

function durationLabel(seconds: number | null): string {
  if (!seconds) return "No recorded duration";
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

export function FaceToFaceCompanion({
  interactionId,
}: {
  interactionId: string;
}) {
  const [interaction, setInteraction] = useState<Interaction | null>(null);
  const [brief, setBrief] = useState<PreInteractionBriefResponse | null>(null);
  const [markers, setMarkers] = useState<InteractionMarker[]>([]);
  const [recordings, setRecordings] = useState<RecordingSession[]>([]);
  const [visuals, setVisuals] = useState<VisualEvidence[]>([]);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [captureChoice, setCaptureChoice] =
    useState<CaptureChoice>("undecided");
  const [showMarkers, setShowMarkers] = useState(false);
  const [showVisuals, setShowVisuals] = useState(false);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recordingActivity, setRecordingActivity] =
    useState<RecordingActivity | null>(null);
  const elapsedSecondsRef = useRef(0);

  const fetchCompanion = useCallback(async () => {
    const [loadedInteraction, loadedBrief, loadedMarkers, loadedCapabilities] =
      await Promise.all([
        apiRequest<Interaction>(`/api/v1/interactions/${interactionId}`),
        apiRequest<PreInteractionBriefResponse>(
          `/api/v1/interactions/${interactionId}/companion/brief`,
        ),
        apiRequest<InteractionMarker[]>(
          `/api/v1/interactions/${interactionId}/companion/markers`,
        ),
        apiRequest<Capabilities>("/api/v1/beta/capabilities"),
      ]);
    const [loadedRecordings, loadedVisuals] = await Promise.all([
      loadedCapabilities.featureFlags.recordingCapture === true
        ? apiRequest<RecordingSession[]>(
            `/api/v1/interactions/${interactionId}/recordings`,
          )
        : Promise.resolve([]),
      loadedCapabilities.featureFlags.visualEvidence === true
        ? apiRequest<VisualEvidence[]>(
            `/api/v1/interactions/${interactionId}/visual-evidence`,
          )
        : Promise.resolve([]),
    ]);
    return {
      interaction: loadedInteraction,
      brief: loadedBrief,
      markers: loadedMarkers,
      recordings: loadedRecordings,
      visuals: loadedVisuals,
      capabilities: loadedCapabilities,
    };
  }, [interactionId]);

  const applyLoaded = useCallback(
    (loaded: Awaited<ReturnType<typeof fetchCompanion>>) => {
      setInteraction(loaded.interaction);
      setBrief(loaded.brief);
      setMarkers(loaded.markers);
      setRecordings(loaded.recordings);
      setVisuals(loaded.visuals);
      setCapabilities(loaded.capabilities);
      const stored = window.sessionStorage.getItem(
        captureStorageKey(interactionId),
      );
      if (stored === "recording" || stored === "passive") {
        setCaptureChoice(stored);
      }
    },
    [interactionId],
  );

  useEffect(() => {
    let cancelled = false;
    void fetchCompanion()
      .then((loaded) => {
        if (!cancelled) applyLoaded(loaded);
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "The Companion could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyLoaded, fetchCompanion]);

  function chooseCapture(choice: Exclude<CaptureChoice, "undecided">) {
    setCaptureChoice(choice);
    window.sessionStorage.setItem(captureStorageKey(interactionId), choice);
    setMessage(
      choice === "passive"
        ? "Passive Companion is active. RevenueOS is not recording or listening."
        : "Recording controls are ready. Consent must be confirmed before microphone access is requested.",
    );
  }

  async function startInteraction() {
    setWorking(true);
    setError(null);
    try {
      const started = await apiRequest<Interaction>(
        `/api/v1/interactions/${interactionId}/start`,
        {
          method: "POST",
          body: JSON.stringify({ actualStartAt: new Date().toISOString() }),
        },
      );
      setInteraction(started);
      setMessage(
        started.interactionType === "online_meeting"
          ? "Meeting started. Passive Companion is active; RevenueOS is not recording or listening."
          : "Interaction started. Choose how you want Companion to help.",
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The interaction could not be started.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function prepareBrief() {
    setWorking(true);
    setError(null);
    try {
      setBrief(
        await apiRequest<PreInteractionBriefRequestResponse>(
          `/api/v1/interactions/${interactionId}/companion/brief`,
          { method: "POST", body: "{}" },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The brief could not be prepared.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function addMarker(markerType: InteractionMarkerType) {
    setWorking(true);
    setError(null);
    try {
      const marker = await apiRequest<InteractionMarker>(
        `/api/v1/interactions/${interactionId}/companion/markers`,
        {
          method: "POST",
          body: JSON.stringify({
            markerType,
            recordingOffsetMs:
              recordingActivity?.active && elapsedSecondsRef.current > 0
                ? elapsedSecondsRef.current * 1_000
                : null,
            idempotencyKey: requestKey("companion-marker"),
          }),
        },
      );
      setMarkers((current) => [...current, marker]);
      setMessage(`${humanise(markerType)} marked.`);
      setShowMarkers(false);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The marker could not be saved.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function deleteMarker(marker: InteractionMarker) {
    setWorking(true);
    setError(null);
    try {
      await apiRequest(
        `/api/v1/interactions/${interactionId}/companion/markers/${marker.id}`,
        { method: "DELETE" },
      );
      setMarkers((current) => current.filter((item) => item.id !== marker.id));
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The marker could not be removed.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function endInteraction() {
    if (recordingActivity?.blocksInteractionCompletion) {
      setError(
        "Stop and finish the recording upload before ending the interaction.",
      );
      return;
    }
    setWorking(true);
    setError(null);
    try {
      const completed = await apiRequest<Interaction>(
        `/api/v1/interactions/${interactionId}/complete`,
        { method: "POST", body: "{}" },
      );
      setInteraction(completed);
      setMessage(
        completed.interactionType === "online_meeting"
          ? "Meeting ended. Choose an authorised capture path while the context is fresh."
          : "Interaction completed. Capture anything the recording missed.",
      );
      applyLoaded(await fetchCompanion());
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The interaction could not be completed.",
      );
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <p role="status">Loading mobile Companion…</p>;
  if (!interaction) {
    return (
      <div role="alert" className="rounded-2xl bg-red-50 p-5 text-red-900">
        {error ?? "The interaction was not found."}
      </div>
    );
  }

  const phase =
    interaction.lifecycleStatus === "planned"
      ? "BEFORE"
      : interaction.lifecycleStatus === "in_progress"
        ? "DURING"
        : "AFTER";
  const recordingEnabled = capabilities?.featureFlags.recordingCapture === true;
  const visualEnabled = capabilities?.featureFlags.visualEvidence === true;
  const latestRecording = recordings[0] ?? recordingActivity?.recording ?? null;
  const canUseBrowserRecording = !["phone_call", "online_meeting"].includes(
    interaction.interactionType,
  );
  const effectiveCaptureChoice = canUseBrowserRecording
    ? captureChoice
    : "passive";

  return (
    <main className="mx-auto max-w-3xl pb-24" aria-labelledby="companion-title">
      <div className="-mx-4 border-b border-slate-200 bg-slate-50 px-4 py-3 sm:mx-0 sm:rounded-2xl">
        <div className="flex items-center justify-between gap-3">
          <Link
            className="text-sm font-bold text-teal-800"
            href={`/interactions/${interactionId}`}
          >
            Back
          </Link>
          <span className="rounded-full bg-slate-950 px-3 py-1 text-xs font-bold tracking-[0.16em] text-white">
            {phase}
          </span>
        </div>
        <h1
          id="companion-title"
          className="mt-2 truncate text-xl font-semibold text-slate-950"
        >
          {interaction.title}
        </h1>
      </div>

      {message ? (
        <p
          role="status"
          className="mt-4 rounded-xl bg-teal-50 p-4 text-sm text-teal-950"
        >
          {message}
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-red-50 p-4 text-sm text-red-900"
        >
          {error}
        </p>
      ) : null}

      {interaction.lifecycleStatus === "cancelled" ? (
        <section className="form-card mt-5">
          <h2 className="text-xl font-semibold">Interaction cancelled</h2>
          <p className="mt-2 text-sm text-slate-600">
            Capture controls are unavailable.
          </p>
        </section>
      ) : phase === "BEFORE" ? (
        <BeforePhase
          interaction={interaction}
          brief={brief}
          working={working}
          onPrepare={() => void prepareBrief()}
          onStart={() => void startInteraction()}
        />
      ) : phase === "DURING" ? (
        <>
          {effectiveCaptureChoice === "undecided" ? (
            <CaptureChoicePanel
              interaction={interaction}
              recordingEnabled={recordingEnabled}
              onChoose={chooseCapture}
            />
          ) : null}

          {effectiveCaptureChoice === "recording" &&
          recordingEnabled &&
          canUseBrowserRecording ? (
            <div className="mt-5">
              <RecordingFoundation
                interactionId={interactionId}
                interactionType={interaction.interactionType}
                lifecycleStatus={interaction.lifecycleStatus}
                showTranscript={false}
                fallbackHref="#companion-controls"
                fallbackLabel="Continue with passive Companion"
                onElapsedSecondsChange={(seconds) => {
                  elapsedSecondsRef.current = seconds;
                }}
                onActivityChange={setRecordingActivity}
                onFinalized={(finalized) => {
                  setRecordings((current) => [
                    finalized,
                    ...current.filter((item) => item.id !== finalized.id),
                  ]);
                }}
              />
            </div>
          ) : null}

          {effectiveCaptureChoice === "passive" ? (
            <section className="mt-5 rounded-3xl border border-teal-200 bg-teal-50 p-5">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-800">
                Passive Companion
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                No recording or listening
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-700">
                {interaction.interactionType === "phone_call"
                  ? "This browser cannot reliably record the same phone call, so no recording or listening has started."
                  : interaction.interactionType === "online_meeting"
                    ? "A browser microphone is not reliable system-audio capture for an online meeting, so no recording or listening has started."
                    : "Add a photo or marker only when it is safe and appropriate. Markers contain a type and timestamp, never a note."}
              </p>
            </section>
          ) : null}

          {effectiveCaptureChoice !== "undecided" ? (
            <CompanionControls
              markers={markers}
              working={working}
              visualEnabled={visualEnabled}
              showMarkers={showMarkers}
              onToggleMarkers={() => setShowMarkers((value) => !value)}
              onToggleVisuals={() => setShowVisuals((value) => !value)}
              onAddMarker={(type) => void addMarker(type)}
              onDeleteMarker={(marker) => void deleteMarker(marker)}
              onEnd={() => void endInteraction()}
              endLabel={
                interaction.interactionType === "online_meeting"
                  ? "End meeting"
                  : "End interaction"
              }
              endDisabled={
                working ||
                recordingActivity?.blocksInteractionCompletion === true
              }
            />
          ) : null}

          {showVisuals && visualEnabled ? (
            <div className="mt-5" id="companion-visuals">
              <VisualEvidenceCapture
                interactionId={interactionId}
                interactionType={interaction.interactionType}
                lifecycleStatus={interaction.lifecycleStatus}
              />
            </div>
          ) : null}
        </>
      ) : (
        <AfterPhase
          interaction={interaction}
          latestRecording={latestRecording}
          markerCount={markers.length}
          visualCount={visuals.length}
          visualEnabled={visualEnabled}
          debriefEnabled={capabilities?.featureFlags.aiDebrief === true}
          showVisuals={showVisuals}
          onToggleVisuals={() => setShowVisuals((value) => !value)}
        />
      )}

      {phase === "AFTER" && showVisuals && visualEnabled ? (
        <div className="mt-5">
          <VisualEvidenceCapture
            interactionId={interactionId}
            interactionType={interaction.interactionType}
            lifecycleStatus={interaction.lifecycleStatus}
          />
        </div>
      ) : null}
      {phase === "AFTER" &&
      interaction.interactionType === "online_meeting" &&
      capabilities?.featureFlags.onlineMeetingCapture === true ? (
        <div className="mt-5" id="online-meeting-capture">
          <OnlineMeetingCapture interaction={interaction} />
        </div>
      ) : null}
      {phase === "AFTER" && capabilities?.featureFlags.aiDebrief === true ? (
        <div className="mt-5" id="companion-debrief">
          <PostInteractionCapture
            interactionId={interactionId}
            interactionType={interaction.interactionType}
          />
        </div>
      ) : null}
    </main>
  );
}

function BeforePhase({
  interaction,
  brief,
  working,
  onPrepare,
  onStart,
}: {
  interaction: Interaction;
  brief: PreInteractionBriefResponse | null;
  working: boolean;
  onPrepare(): void;
  onStart(): void;
}) {
  const content = brief?.state === "completed" ? brief.brief : null;
  return (
    <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-800">
        30-second brief
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
        <span className="rounded-full bg-teal-50 px-3 py-1 text-teal-900">
          {humanise(interaction.interactionType)}
        </span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
          {formatInteractionDate(interaction.scheduledStartAt)}
        </span>
      </div>
      {content ? (
        <div className="mt-5 space-y-5">
          <div>
            <p className="text-sm text-slate-500">
              {[content.companyName, content.opportunityName]
                .filter(Boolean)
                .join(" · ") || "Linked interaction context"}
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-slate-950">
              {content.headline}
            </h2>
            {content.participants.length ? (
              <p className="mt-2 text-sm text-slate-600">
                {content.participants
                  .map((item) => `${item.name} · ${item.role}`)
                  .join("; ")}
              </p>
            ) : null}
          </div>
          <BriefList
            title="Top objectives"
            items={content.objectives.slice(0, 3).map((item) => item.objective)}
          />
          <BriefList
            title="Questions to ask"
            items={content.questionsToAsk
              .slice(0, 3)
              .map((item) => item.question)}
            numbered
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <BriefHighlight
              title="Highest risk"
              text={content.risksToWatch[0]?.risk ?? "No validated risk yet."}
            />
            <BriefHighlight
              title="Next best action"
              text={content.nextBestAction ?? "No validated next action yet."}
            />
            <BriefHighlight
              title="Recent change"
              text={
                content.recentChanges[0]?.change ??
                "No validated recent change."
              }
            />
            <BriefHighlight
              title="Success"
              text={
                content.successCriteria[0] ?? "Confirm an observable next step."
              }
            />
          </div>
        </div>
      ) : (
        <div className="mt-5 rounded-2xl border border-dashed border-slate-300 p-5">
          <h2 className="font-semibold text-slate-950">
            Preparation brief not ready
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {brief?.safeMessage ??
              "Prepare a source-aware brief before the interaction, or continue without one."}
          </p>
          {brief?.generationAvailable ? (
            <button
              type="button"
              className="secondary-button mt-4 min-h-12"
              disabled={working}
              onClick={onPrepare}
            >
              {working ? "Preparing…" : "Prepare brief"}
            </button>
          ) : null}
        </div>
      )}
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          className="primary-button min-h-14 text-base"
          disabled={working}
          onClick={onStart}
        >
          {working
            ? "Starting…"
            : interaction.interactionType === "online_meeting"
              ? "Start meeting"
              : "Start interaction"}
        </button>
        {interaction.interactionType === "online_meeting" &&
        interaction.meetingUrl ? (
          <a
            className="secondary-button min-h-14 text-center text-base"
            href={interaction.meetingUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open meeting
          </a>
        ) : null}
        <Link
          className="secondary-button min-h-14 text-center text-base"
          href={`/interactions/${interaction.id}#preparation`}
        >
          Open full brief
        </Link>
      </div>
    </section>
  );
}

function BriefList({
  title,
  items,
  numbered = false,
}: {
  title: string;
  items: string[];
  numbered?: boolean;
}) {
  const List = numbered ? "ol" : "ul";
  return (
    <div>
      <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {title}
      </h3>
      <List
        className={`mt-2 space-y-2 text-sm text-slate-800 ${numbered ? "list-decimal" : "list-disc"} pl-5`}
      >
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </List>
    </div>
  );
}

function BriefHighlight({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {title}
      </h3>
      <p className="mt-2 text-sm leading-6 text-slate-800">{text}</p>
    </div>
  );
}

function CaptureChoicePanel({
  interaction,
  recordingEnabled,
  onChoose,
}: {
  interaction: Interaction;
  recordingEnabled: boolean;
  onChoose(choice: "recording" | "passive"): void;
}) {
  const browserRecordingExcluded = ["phone_call", "online_meeting"].includes(
    interaction.interactionType,
  );
  return (
    <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-800">
        Choose deliberately
      </p>
      <h2 className="mt-2 text-2xl font-semibold text-slate-950">
        How should Companion help?
      </h2>
      {interaction.interactionType === "executive_lunch" ? (
        <p className="mt-3 rounded-xl bg-amber-50 p-4 text-sm text-amber-950">
          Passive Companion is recommended for an executive lunch. Keep the
          device unobtrusive.
        </p>
      ) : null}
      {browserRecordingExcluded ? (
        <div className="mt-4 rounded-xl bg-indigo-50 p-4 text-sm leading-6 text-indigo-950">
          {interaction.interactionType === "phone_call"
            ? "This browser cannot reliably record the same phone call. No recording will start."
            : "A browser microphone is not reliable system-audio capture for an online meeting. No recording will start."}
        </div>
      ) : null}
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {!browserRecordingExcluded && recordingEnabled ? (
          <button
            type="button"
            className="primary-button min-h-16 text-base"
            onClick={() => onChoose("recording")}
          >
            Record interaction
          </button>
        ) : null}
        <button
          type="button"
          className="secondary-button min-h-16 text-base"
          onClick={() => onChoose("passive")}
        >
          Continue without recording
        </button>
      </div>
    </section>
  );
}

function CompanionControls({
  markers,
  working,
  visualEnabled,
  showMarkers,
  onToggleMarkers,
  onToggleVisuals,
  onAddMarker,
  onDeleteMarker,
  onEnd,
  endDisabled,
  endLabel,
}: {
  markers: InteractionMarker[];
  working: boolean;
  visualEnabled: boolean;
  showMarkers: boolean;
  onToggleMarkers(): void;
  onToggleVisuals(): void;
  onAddMarker(type: InteractionMarkerType): void;
  onDeleteMarker(marker: InteractionMarker): void;
  onEnd(): void;
  endDisabled: boolean;
  endLabel: string;
}) {
  return (
    <section
      id="companion-controls"
      className="mt-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {visualEnabled ? (
          <button
            type="button"
            className="secondary-button min-h-16 text-base"
            onClick={onToggleVisuals}
          >
            Add photo
          </button>
        ) : null}
        <button
          type="button"
          className="secondary-button min-h-16 text-base"
          onClick={onToggleMarkers}
        >
          Add marker
        </button>
        <button
          type="button"
          className="primary-button min-h-16 text-base"
          disabled={endDisabled}
          onClick={onEnd}
        >
          {endLabel}
        </button>
      </div>
      {endDisabled ? (
        <p className="mt-3 text-sm text-amber-900">
          Finish the recording and any queued upload before ending.
        </p>
      ) : null}
      {showMarkers ? (
        <div className="mt-5 border-t border-slate-200 pt-5">
          <h2 className="font-semibold text-slate-950">Mark this moment</h2>
          <p className="mt-1 text-xs text-slate-500">
            Metadata only: marker type, creator, time and recording offset when
            available.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {MARKERS.map((marker) => (
              <button
                key={marker.type}
                type="button"
                disabled={working}
                className="min-h-14 rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-600"
                onClick={() => onAddMarker(marker.type)}
              >
                {marker.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {markers.length ? (
        <div className="mt-5 border-t border-slate-200 pt-4">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
            {markers.length} marker{markers.length === 1 ? "" : "s"}
          </p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {markers.slice(-6).map((marker) => (
              <li
                key={marker.id}
                className="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-800"
              >
                {humanise(marker.markerType)}
                <button
                  type="button"
                  disabled={working}
                  className="rounded px-1 text-red-800 focus:outline-none focus:ring-2 focus:ring-red-700"
                  aria-label={`Remove ${humanise(marker.markerType)} marker`}
                  onClick={() => onDeleteMarker(marker)}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function AfterPhase({
  interaction,
  latestRecording,
  markerCount,
  visualCount,
  visualEnabled,
  debriefEnabled,
  showVisuals,
  onToggleVisuals,
}: {
  interaction: Interaction;
  latestRecording: RecordingSession | null;
  markerCount: number;
  visualCount: number;
  visualEnabled: boolean;
  debriefEnabled: boolean;
  showVisuals: boolean;
  onToggleVisuals(): void;
}) {
  return (
    <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-800">
        Capture summary
      </p>
      <h2 className="mt-2 text-2xl font-semibold text-slate-950">
        Fill the gaps while they are fresh
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {latestRecording
          ? "Direct recording context is used to avoid repeating covered questions. Markers guide the debrief but never become intelligence by themselves."
          : "Use the debrief to capture the outcome in your own words. Markers guide questions but never become intelligence by themselves."}
      </p>
      <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryStat
          label="Recording"
          value={durationLabel(latestRecording?.durationSeconds ?? null)}
        />
        <SummaryStat
          label="Transcription"
          value={
            latestRecording
              ? humanise(latestRecording.transcriptionStatus)
              : "Not recorded"
          }
        />
        <SummaryStat label="Photos" value={String(visualCount)} />
        <SummaryStat label="Markers" value={String(markerCount)} />
      </dl>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {debriefEnabled ? (
          <>
            <a
              className="primary-button min-h-14 text-center text-base"
              href="#companion-debrief"
            >
              Start AI Debrief
            </a>
            <a
              className="secondary-button min-h-14 text-center text-base"
              href="#companion-debrief"
            >
              Add Voice Journal
            </a>
          </>
        ) : null}
        {visualEnabled ? (
          <button
            type="button"
            className="secondary-button min-h-14 text-base"
            onClick={onToggleVisuals}
          >
            {showVisuals ? "Hide photo capture" : "Add visual evidence"}
          </button>
        ) : null}
        {interaction.opportunityId ? (
          <Link
            className="secondary-button min-h-14 text-center text-base"
            href={`/opportunities/${interaction.opportunityId}`}
          >
            Open opportunity workspace
          </Link>
        ) : null}
        <Link
          className="secondary-button min-h-14 text-center text-base"
          href={
            interaction.companyId
              ? `/companies/${interaction.companyId}`
              : "/companies"
          }
        >
          Open Revenue Brain
        </Link>
        <Link
          className="primary-button min-h-14 text-center text-base"
          href={`/interactions/${interaction.id}`}
        >
          Finish
        </Link>
      </div>
    </section>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-2 text-sm font-semibold text-slate-900">{value}</dd>
    </div>
  );
}
