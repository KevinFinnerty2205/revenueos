"use client";

import type {
  CallOutcome,
  Interaction,
  InteractionMarker,
  InteractionMarkerType,
  PreInteractionBriefRequestResponse,
  PreInteractionBriefResponse,
  RecordingSession,
} from "@revenueos/shared";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { PostInteractionCapture } from "@/components/post-interaction-capture";
import { LiveInteractionIntelligence } from "@/components/live-interaction-intelligence";
import { OnlineMeetingCapture } from "@/components/online-meeting-capture";
import {
  ConversationLiveNotes,
  RecordingFoundation,
  type RecordingActivity,
} from "@/components/recording-foundation";
import { VisualEvidenceCapture } from "@/components/visual-evidence-capture";
import { ConversationWorkspaceConflictRecovery } from "@/components/conversation-workspace-conflict-recovery";
import { useVerifiedOrganisation } from "@/components/verified-organisation-context";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import {
  validateCreatedInteractionMarker,
  validateDeletedInteractionMarker,
  validateInteractionMarkers,
} from "@/lib/interaction-marker-identity";
import { decodeInteractionResponse } from "@/lib/interaction-response-identity";
import { formatInteractionDate } from "@/lib/interactions";
import { assertPreInteractionBriefIdentity } from "@/lib/pre-interaction-brief-identity";
import {
  decodeRecordingSessionForInteraction,
  decodeRecordingSessionsForInteraction,
} from "@/lib/recording-session-identity";
import { useConversationWorkspace } from "@/lib/use-conversation-workspace";
import { validateVisualEvidenceListForInteraction } from "@/lib/visual-evidence-identity";

type CaptureChoice = "undecided" | "recording" | "passive";
type CompanionAvailability = "checking" | "ready" | "disabled" | "unavailable";

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

const LIVE_NOTE_CONFLICT_FIELDS = [
  {
    key: "liveNotes" as const,
    label: "Latest saved private note",
    emptyLabel: "The latest saved version has no private note.",
  },
] as const;

const INTERACTION_RESPONSE_ERROR =
  "The interaction response did not match this conversation. Try again.";
const MARKER_LOAD_WARNING =
  "Conversation markers could not be loaded. Your private notes remain available.";
const MARKER_MUTATION_WARNING =
  "The marker change could not be confirmed. Refresh markers to check what was saved.";
const RECORDING_RESPONSE_WARNING =
  "Updated recording details could not be verified. Your private notes remain available.";

function requestKey(prefix: string): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? `${prefix}-${crypto.randomUUID()}`
    : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function captureStorageKey(
  interactionId: string,
  organisationId: string,
  userId: string,
): string {
  return `revenueos:companion:capture-choice:${organisationId}:${userId}:${interactionId}`;
}

function durationLabel(seconds: number | null): string {
  if (!seconds) return "No recorded duration";
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

export function FaceToFaceCompanion({
  interactionId,
  ...props
}: FaceToFaceCompanionProps) {
  const verifiedIdentity = useVerifiedOrganisation();

  if (verifiedIdentity.status === "loading") {
    return <p role="status">Verifying access to notes &amp; capture…</p>;
  }
  if (verifiedIdentity.status !== "available") {
    return (
      <section
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-950"
      >
        <p>Notes &amp; capture are temporarily unavailable.</p>
        <button
          type="button"
          className="secondary-button mt-3"
          onClick={verifiedIdentity.reload}
        >
          Try again
        </button>
      </section>
    );
  }

  const sessionKey = [
    interactionId,
    verifiedIdentity.organisationId,
    verifiedIdentity.userId,
    verifiedIdentity.identityKey,
  ].join(":");

  return (
    <FaceToFaceCompanionSession
      key={sessionKey}
      interactionId={interactionId}
      organisationId={verifiedIdentity.organisationId}
      userId={verifiedIdentity.userId}
      {...props}
    />
  );
}

interface FaceToFaceCompanionProps {
  interactionId: string;
  initialInteraction?: Interaction;
  embedded?: boolean;
  onInteractionChange?: (interaction: Interaction) => void;
  onOpenPreparation?: () => void;
  onOpenReview?: () => void;
  briefRefreshKey?: number;
}

interface FaceToFaceCompanionSessionProps extends FaceToFaceCompanionProps {
  organisationId: string;
  userId: string;
}

function FaceToFaceCompanionSession({
  interactionId,
  organisationId,
  userId,
  initialInteraction,
  embedded = false,
  onInteractionChange,
  onOpenPreparation,
  onOpenReview,
  briefRefreshKey = 0,
}: FaceToFaceCompanionSessionProps) {
  const seededInteraction = decodeInteractionResponse(initialInteraction, {
    interactionId,
    organisationId,
  });
  const [interaction, setInteraction] = useState<Interaction | null>(
    seededInteraction,
  );
  const [brief, setBrief] = useState<PreInteractionBriefResponse | null>(null);
  const [markers, setMarkers] = useState<InteractionMarker[]>([]);
  const [recordings, setRecordings] = useState<RecordingSession[]>([]);
  const [visualCount, setVisualCount] = useState(0);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [companionAvailability, setCompanionAvailability] =
    useState<CompanionAvailability>("checking");
  const [companionWarnings, setCompanionWarnings] = useState<string[]>([]);
  const [markersAvailable, setMarkersAvailable] = useState(false);
  const [markersNeedRefresh, setMarkersNeedRefresh] = useState(false);
  const [captureChoice, setCaptureChoice] =
    useState<CaptureChoice>("undecided");
  const [showMarkers, setShowMarkers] = useState(false);
  const [showVisuals, setShowVisuals] = useState(false);
  const [loading, setLoading] = useState(seededInteraction === null);
  const [interactionLoadRetryKey, setInteractionLoadRetryKey] = useState(0);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recordingActivity, setRecordingActivity] =
    useState<RecordingActivity | null>(null);
  const sessionActiveRef = useRef(true);
  const elapsedSecondsRef = useRef(0);
  const liveNotesRevisionRef = useRef(0);
  const personalWorkspace = useConversationWorkspace({ interactionId });
  const liveNotes = personalWorkspace.values.liveNotes;
  const updateLiveNotes = (value: string) => {
    liveNotesRevisionRef.current += 1;
    personalWorkspace.setValues((current) => ({
      ...current,
      liveNotes: value,
    }));
  };
  const liveNotesStatus = personalWorkspace.loading
    ? "Loading your private notes…"
    : personalWorkspace.workspace === null && personalWorkspace.error
      ? "Private notes are temporarily unavailable. Try again before entering or saving notes."
      : personalWorkspace.saveState === "saving"
        ? "Saving private notes…"
        : personalWorkspace.saveState === "saved"
          ? personalWorkspace.dirtyFields.liveNotes
            ? "An earlier note version was saved. Newer changes remain unsaved."
            : "Private notes saved."
          : personalWorkspace.saveState === "conflict"
            ? "Another session saved a different version. Your local text is unchanged; compare both versions below."
            : personalWorkspace.saveState === "failed"
              ? "Private notes could not be saved. Your local text is still visible."
              : personalWorkspace.error
                ? personalWorkspace.error
                : "Private to you until you deliberately include something in review.";

  useLayoutEffect(() => {
    sessionActiveRef.current = true;
    return () => {
      sessionActiveRef.current = false;
    };
  }, []);

  const fetchCompanion = useCallback(async () => {
    let loadedCapabilities: Capabilities;
    try {
      loadedCapabilities = await apiRequest<Capabilities>(
        "/api/v1/beta/capabilities",
      );
    } catch {
      return {
        availability: "unavailable" as const,
        brief: null,
        markers: null,
        markersAvailable: false,
        recordings: null,
        visualCount: null,
        capabilities: null,
        warnings: [
          "Companion availability could not be checked. Your private notes remain available.",
        ],
      };
    }
    if (loadedCapabilities.featureFlags.aiCompanion !== true) {
      return {
        availability: "disabled" as const,
        brief: null,
        markers: [],
        markersAvailable: false,
        recordings: [],
        visualCount: 0,
        capabilities: loadedCapabilities,
        warnings: [],
      };
    }
    const interactionPath = `/api/v1/interactions/${encodeURIComponent(interactionId)}`;
    const [briefResult, markersResult, recordingsResult, visualsResult] =
      await Promise.allSettled([
        apiRequest<PreInteractionBriefResponse>(
          `${interactionPath}/companion/brief`,
        ).then((response) => {
          assertPreInteractionBriefIdentity(response, interactionId);
          return response;
        }),
        apiRequest<unknown>(`${interactionPath}/companion/markers`).then(
          (response) => validateInteractionMarkers(response, interactionId),
        ),
        loadedCapabilities.featureFlags.recordingCapture === true
          ? apiRequest<unknown>(`${interactionPath}/recordings`).then(
              (response) =>
                decodeRecordingSessionsForInteraction(response, interactionId),
            )
          : Promise.resolve<RecordingSession[]>([]),
        loadedCapabilities.featureFlags.visualEvidence === true
          ? apiRequest<unknown>(`${interactionPath}/visual-evidence`).then(
              (response) =>
                validateVisualEvidenceListForInteraction(
                  response,
                  interactionId,
                ),
            )
          : Promise.resolve([]),
      ]);
    const warnings: string[] = [];
    if (briefResult.status === "rejected") {
      warnings.push(
        "Preparation guidance could not be loaded. Your private notes remain available.",
      );
    }
    if (markersResult.status === "rejected") {
      warnings.push(MARKER_LOAD_WARNING);
    }
    if (recordingsResult.status === "rejected") {
      warnings.push(
        "Previous recording details could not be loaded. Your private notes remain available.",
      );
    }
    if (visualsResult.status === "rejected") {
      warnings.push(
        "Previous visual evidence could not be loaded. Your private notes remain available.",
      );
    }
    return {
      availability: "ready" as const,
      brief: briefResult.status === "fulfilled" ? briefResult.value : null,
      markers:
        markersResult.status === "fulfilled" ? markersResult.value : null,
      markersAvailable: markersResult.status === "fulfilled",
      recordings:
        recordingsResult.status === "fulfilled" ? recordingsResult.value : null,
      visualCount:
        visualsResult.status === "fulfilled"
          ? visualsResult.value.length
          : null,
      capabilities: loadedCapabilities,
      warnings,
    };
  }, [interactionId]);

  const applyLoaded = useCallback(
    (loaded: Awaited<ReturnType<typeof fetchCompanion>>) => {
      setBrief(loaded.brief);
      if (loaded.markers !== null) {
        setMarkers(loaded.markers);
        setMarkersAvailable(loaded.markersAvailable);
      }
      setMarkersNeedRefresh(loaded.markers === null);
      if (loaded.recordings !== null) setRecordings(loaded.recordings);
      if (loaded.visualCount !== null) setVisualCount(loaded.visualCount);
      setCapabilities(loaded.capabilities);
      setCompanionAvailability(loaded.availability);
      setCompanionWarnings(loaded.warnings);
      const stored = window.sessionStorage.getItem(
        captureStorageKey(interactionId, organisationId, userId),
      );
      if (stored === "recording" || stored === "passive") {
        setCaptureChoice(stored);
      }
    },
    [interactionId, organisationId, userId],
  );

  useEffect(() => {
    if (seededInteraction) return;
    let cancelled = false;
    void apiRequest<unknown>(
      `/api/v1/interactions/${encodeURIComponent(interactionId)}`,
    )
      .then((payload) => {
        const loadedInteraction = decodeInteractionResponse(payload, {
          interactionId,
          organisationId,
        });
        if (loadedInteraction === null) {
          throw new Error(INTERACTION_RESPONSE_ERROR);
        }
        if (!cancelled && sessionActiveRef.current) {
          setInteraction(loadedInteraction);
          onInteractionChange?.(loadedInteraction);
          setError(null);
        }
      })
      .catch((requestError: unknown) => {
        if (!cancelled && sessionActiveRef.current) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "The Companion could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (!cancelled && sessionActiveRef.current) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    interactionId,
    interactionLoadRetryKey,
    onInteractionChange,
    organisationId,
    seededInteraction,
  ]);

  useEffect(() => {
    let cancelled = false;
    void fetchCompanion().then((loaded) => {
      if (!cancelled) applyLoaded(loaded);
    });
    return () => {
      cancelled = true;
    };
  }, [applyLoaded, fetchCompanion]);

  const appendCompanionWarning = useCallback((warning: string) => {
    setCompanionWarnings((current) =>
      current.includes(warning) ? current : [...current, warning],
    );
  }, []);

  const handleRecordingActivityChange = useCallback(
    (activity: RecordingActivity) => {
      if (!sessionActiveRef.current) return;
      try {
        if (activity.recording !== null) {
          decodeRecordingSessionForInteraction(
            activity.recording,
            interactionId,
          );
        }
        setRecordingActivity(activity);
      } catch {
        // Keep a completion guard until a later verified activity update can clear it.
        setRecordingActivity((current) => ({
          ...activity,
          active: activity.active || current?.active === true,
          blocksInteractionCompletion:
            activity.blocksInteractionCompletion ||
            current?.blocksInteractionCompletion === true,
          recording: current?.recording ?? null,
        }));
        appendCompanionWarning(RECORDING_RESPONSE_WARNING);
      }
    },
    [appendCompanionWarning, interactionId],
  );

  const handleRecordingFinalized = useCallback(
    (finalized: RecordingSession) => {
      if (!sessionActiveRef.current) return;
      try {
        const verified = decodeRecordingSessionForInteraction(
          finalized,
          interactionId,
          "finalised",
        );
        setRecordings((current) => [
          verified,
          ...current.filter((item) => item.id !== verified.id),
        ]);
      } catch {
        appendCompanionWarning(RECORDING_RESPONSE_WARNING);
      }
    },
    [appendCompanionWarning, interactionId],
  );

  useEffect(() => {
    if (briefRefreshKey === 0 || companionAvailability !== "ready") return;
    const controller = new AbortController();
    void apiRequest<PreInteractionBriefResponse>(
      `/api/v1/interactions/${interactionId}/companion/brief`,
      { signal: controller.signal },
    )
      .then((updated) => {
        if (!controller.signal.aborted) {
          assertPreInteractionBriefIdentity(updated, interactionId);
          setBrief(updated);
        }
      })
      .catch((requestError: unknown) => {
        if (
          !controller.signal.aborted &&
          !(
            requestError instanceof DOMException &&
            requestError.name === "AbortError"
          )
        ) {
          appendCompanionWarning(
            "The refreshed preparation brief could not be loaded. Your private notes remain available.",
          );
        }
      });
    return () => controller.abort();
  }, [
    appendCompanionWarning,
    briefRefreshKey,
    companionAvailability,
    interactionId,
  ]);

  function chooseCapture(choice: Exclude<CaptureChoice, "undecided">) {
    setCaptureChoice(choice);
    window.sessionStorage.setItem(
      captureStorageKey(interactionId, organisationId, userId),
      choice,
    );
    setMessage(
      choice === "passive"
        ? "Passive Companion is active. Oryntela is not recording or listening."
        : interaction?.interactionType === "online_meeting"
          ? "Meeting audio controls are ready. Choose shared audio plus microphone or microphone only, then confirm consent before access is requested."
          : "Recording controls are ready. Consent must be confirmed before microphone access is requested.",
    );
  }

  async function startInteraction() {
    if (interaction === null) return;
    const baseline = interaction;
    setWorking(true);
    setError(null);
    try {
      const payload = await apiRequest<unknown>(
        `/api/v1/interactions/${encodeURIComponent(interactionId)}/start`,
        {
          method: "POST",
          body: JSON.stringify({ actualStartAt: new Date().toISOString() }),
        },
      );
      if (!sessionActiveRef.current) return;
      const started = decodeInteractionResponse(payload, {
        interactionId,
        organisationId,
        baseline,
        expectedLifecycleStatus: "in_progress",
      });
      if (started === null) {
        setError(INTERACTION_RESPONSE_ERROR);
        return;
      }
      setInteraction(started);
      onInteractionChange?.(started);
      setMessage(
        companionAvailability === "ready"
          ? started.interactionType === "online_meeting"
            ? "Meeting started. Choose whether to capture meeting audio or continue without recording."
            : "Interaction started. Choose how you want Companion to help."
          : "Interaction started. Private notes are ready; optional Companion controls remain unavailable.",
      );
    } catch (requestError: unknown) {
      if (!sessionActiveRef.current) return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The interaction could not be started.",
      );
    } finally {
      if (sessionActiveRef.current) setWorking(false);
    }
  }

  async function prepareBrief() {
    setWorking(true);
    setError(null);
    try {
      const prepared = await apiRequest<PreInteractionBriefRequestResponse>(
        `/api/v1/interactions/${interactionId}/companion/brief`,
        { method: "POST", body: "{}" },
      );
      assertPreInteractionBriefIdentity(prepared, interactionId);
      if (!sessionActiveRef.current) return;
      setBrief(prepared);
    } catch (requestError: unknown) {
      if (!sessionActiveRef.current) return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The brief could not be prepared.",
      );
    } finally {
      if (sessionActiveRef.current) setWorking(false);
    }
  }

  async function addMarker(markerType: InteractionMarkerType) {
    if (!markersAvailable || markersNeedRefresh) return;
    setWorking(true);
    setError(null);
    setMessage(null);
    const recordingOffsetMs =
      recordingActivity?.active && elapsedSecondsRef.current > 0
        ? elapsedSecondsRef.current * 1_000
        : null;
    try {
      const response = await apiRequest<unknown>(
        `/api/v1/interactions/${encodeURIComponent(interactionId)}/companion/markers`,
        {
          method: "POST",
          body: JSON.stringify({
            markerType,
            recordingOffsetMs,
            idempotencyKey: requestKey("companion-marker"),
          }),
        },
      );
      if (!sessionActiveRef.current) return;
      const marker = validateCreatedInteractionMarker(response, {
        interactionId,
        createdByUserId: userId,
        markerType,
        recordingOffsetMs,
      });
      const existing = markers.find(({ id }) => id === marker.id);
      if (
        existing &&
        (existing.createdByUserId !== marker.createdByUserId ||
          existing.markerType !== marker.markerType ||
          existing.recordingOffsetMs !== marker.recordingOffsetMs ||
          existing.createdAt !== marker.createdAt)
      ) {
        throw new Error(MARKER_MUTATION_WARNING);
      }
      if (!existing) setMarkers((current) => [...current, marker]);
      setMessage(`${humanise(markerType)} marked.`);
      setShowMarkers(false);
    } catch {
      if (!sessionActiveRef.current) return;
      setMarkersNeedRefresh(true);
      setError(MARKER_MUTATION_WARNING);
    } finally {
      if (sessionActiveRef.current) setWorking(false);
    }
  }

  async function deleteMarker(marker: InteractionMarker) {
    if (!markersAvailable || markersNeedRefresh) return;
    setWorking(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiRequest<unknown>(
        `/api/v1/interactions/${encodeURIComponent(interactionId)}/companion/markers/${encodeURIComponent(marker.id)}`,
        { method: "DELETE" },
      );
      if (!sessionActiveRef.current) return;
      validateDeletedInteractionMarker(response, marker.id);
      setMarkers((current) => current.filter((item) => item.id !== marker.id));
    } catch {
      if (!sessionActiveRef.current) return;
      setMarkersNeedRefresh(true);
      setError(MARKER_MUTATION_WARNING);
    } finally {
      if (sessionActiveRef.current) setWorking(false);
    }
  }

  async function refreshMarkers() {
    setWorking(true);
    try {
      const response = await apiRequest<unknown>(
        `/api/v1/interactions/${encodeURIComponent(interactionId)}/companion/markers`,
      );
      if (!sessionActiveRef.current) return;
      setMarkers(validateInteractionMarkers(response, interactionId));
      setMarkersAvailable(true);
      setMarkersNeedRefresh(false);
      setError((current) =>
        current === MARKER_MUTATION_WARNING ? null : current,
      );
      setCompanionWarnings((current) =>
        current.filter((warning) => warning !== MARKER_LOAD_WARNING),
      );
    } catch {
      if (!sessionActiveRef.current) return;
      appendCompanionWarning(MARKER_LOAD_WARNING);
    } finally {
      if (sessionActiveRef.current) setWorking(false);
    }
  }

  async function endInteraction(callOutcome?: CallOutcome) {
    if (recordingActivity?.blocksInteractionCompletion) {
      setError(
        "Stop and finish the recording upload before ending the interaction.",
      );
      return;
    }
    if (interaction === null) return;
    const baseline = interaction;
    setWorking(true);
    setError(null);
    try {
      if (personalWorkspace.dirtyFields.liveNotes) {
        const revisionAtSaveStart = liveNotesRevisionRef.current;
        const notesSaved = await personalWorkspace.save();
        if (!sessionActiveRef.current) return;
        if (!notesSaved) {
          setError(
            "Your private notes could not be saved, so the interaction remains open. Resolve the note error and try again.",
          );
          return;
        }
        if (liveNotesRevisionRef.current !== revisionAtSaveStart) {
          setError(
            "Your private notes changed while saving, so the interaction remains open. Save the newer note version and try again.",
          );
          return;
        }
      }
      const payload = await apiRequest<unknown>(
        `/api/v1/interactions/${encodeURIComponent(interactionId)}/complete`,
        {
          method: "POST",
          body: JSON.stringify(callOutcome ? { callOutcome } : {}),
        },
      );
      if (!sessionActiveRef.current) return;
      const completed = decodeInteractionResponse(payload, {
        interactionId,
        organisationId,
        baseline,
        expectedLifecycleStatus: "completed",
      });
      if (completed === null) {
        setError(INTERACTION_RESPONSE_ERROR);
        return;
      }
      setInteraction(completed);
      onInteractionChange?.(completed);
      setMessage(
        completed.interactionType === "online_meeting"
          ? "Meeting ended. Choose an authorised capture path while the context is fresh."
          : "Interaction completed. Capture anything the recording missed.",
      );
      const loaded = await fetchCompanion();
      if (!sessionActiveRef.current) return;
      applyLoaded(loaded);
    } catch (requestError: unknown) {
      if (!sessionActiveRef.current) return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The interaction could not be completed.",
      );
    } finally {
      if (sessionActiveRef.current) setWorking(false);
    }
  }

  if (loading) return <p role="status">Loading notes & capture…</p>;
  if (!interaction) {
    return (
      <section role="alert" className="rounded-2xl bg-red-50 p-5 text-red-900">
        <p>{error ?? "The interaction was not found."}</p>
        <button
          type="button"
          className="secondary-button mt-3"
          onClick={() => {
            setError(null);
            setLoading(true);
            setInteractionLoadRetryKey((current) => current + 1);
          }}
        >
          Try again
        </button>
      </section>
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
  const latestRecording = recordings[0] ?? null;
  const canUseBrowserRecording = interaction.interactionType !== "phone_call";
  const effectiveCaptureChoice = canUseBrowserRecording
    ? captureChoice
    : "passive";
  const showCanonicalNotes = phase === "BEFORE" || phase === "DURING";
  const privateWorkspaceNeedsRecovery =
    showCanonicalNotes &&
    !personalWorkspace.loading &&
    personalWorkspace.workspace === null &&
    personalWorkspace.error !== null;
  const endLabel = personalWorkspace.dirtyFields.liveNotes
    ? interaction.interactionType === "online_meeting"
      ? "Save notes and end meeting"
      : interaction.interactionType === "phone_call"
        ? "Save notes and end connected call"
        : "Save notes and end interaction"
    : interaction.interactionType === "online_meeting"
      ? "End meeting"
      : interaction.interactionType === "phone_call"
        ? "End connected call"
        : "End interaction";
  const endDisabled =
    working ||
    personalWorkspace.saveState === "conflict" ||
    personalWorkspace.conflictRecovery.state === "saving" ||
    (personalWorkspace.dirtyFields.liveNotes &&
      (personalWorkspace.loading ||
        personalWorkspace.saveState === "saving")) ||
    recordingActivity?.blocksInteractionCompletion === true;

  return (
    <div className="mx-auto max-w-3xl pb-12">
      {!embedded ? (
        <div className="-mx-4 border-b border-slate-200 bg-slate-50 px-4 py-3 sm:mx-0 sm:rounded-2xl">
          <div className="flex items-center justify-between gap-3">
            <Link
              className="text-sm font-bold text-brand-secondary"
              href={`/conversations/${interactionId}`}
            >
              Back
            </Link>
            <span className="rounded-full bg-brand-primary px-3 py-1 text-xs font-bold tracking-[0.16em] text-white">
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
      ) : null}

      {message ? (
        <p
          role="status"
          className="mt-4 rounded-xl bg-brand-secondary/10 p-4 text-sm text-brand-primary"
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
      {companionWarnings.length ? (
        <section
          aria-label="Companion availability"
          className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          <ul className="space-y-1">
            {companionWarnings.map((warning) => (
              <li key={warning} role="status">
                {warning}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {companionAvailability === "ready" && markersNeedRefresh ? (
        <button
          type="button"
          className="secondary-button mt-3"
          disabled={working}
          onClick={() => void refreshMarkers()}
        >
          Refresh markers
        </button>
      ) : null}

      {privateWorkspaceNeedsRecovery ? (
        <section
          role="alert"
          aria-label="Private notes are temporarily unavailable"
          className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-5 text-red-950"
        >
          <h2 className="text-base font-bold">
            Private notes are temporarily unavailable
          </h2>
          <p className="mt-2 text-sm leading-6">
            Try again to load this private workspace before entering or saving
            notes.
          </p>
          <button
            type="button"
            className="secondary-button mt-3"
            onClick={() => void personalWorkspace.reload()}
          >
            Try again
          </button>
        </section>
      ) : null}

      {showCanonicalNotes ? (
        <ConversationLiveNotes
          inputId={`companion-private-notes-${interactionId}`}
          liveNotes={liveNotes}
          onLiveNotesChange={updateLiveNotes}
          onSave={() => void personalWorkspace.save()}
          inputDisabled={
            personalWorkspace.loading || !personalWorkspace.workspace
          }
          saveDisabled={
            personalWorkspace.loading ||
            !personalWorkspace.workspace ||
            personalWorkspace.saveState === "saving" ||
            personalWorkspace.saveState === "conflict"
          }
          status={liveNotesStatus}
        />
      ) : null}

      {showCanonicalNotes ? (
        <ConversationWorkspaceConflictRecovery
          idPrefix={`capture-private-note-conflict-${interactionId}`}
          controller={personalWorkspace}
          fields={LIVE_NOTE_CONFLICT_FIELDS}
          reviewedValues={{ liveNotes }}
          saveLabel="Save reviewed note"
          latestLabel="Use latest saved note"
          onResolved={() => setError(null)}
        />
      ) : null}

      {interaction.lifecycleStatus === "cancelled" ? (
        <section className="form-card mt-5">
          <h2 className="text-xl font-semibold">Interaction cancelled</h2>
          <p className="mt-2 text-sm text-slate-600">
            Capture controls are unavailable.
          </p>
        </section>
      ) : phase === "BEFORE" ? (
        companionAvailability === "ready" ? (
          <BeforePhase
            interaction={interaction}
            brief={brief}
            working={working}
            onPrepare={() => void prepareBrief()}
            onStart={() => void startInteraction()}
            onOpenPreparation={onOpenPreparation}
          />
        ) : (
          <>
            <CompanionAvailabilityNotice availability={companionAvailability} />
            <CoreBeforeControls
              interaction={interaction}
              working={working}
              onStart={() => void startInteraction()}
            />
          </>
        )
      ) : phase === "DURING" ? (
        <>
          {companionAvailability !== "ready" ? (
            <>
              <CompanionAvailabilityNotice
                availability={companionAvailability}
              />
              <CoreDuringControls
                interaction={interaction}
                working={working}
                endDisabled={endDisabled}
                endLabel={endLabel}
                onEnd={(outcome) => void endInteraction(outcome)}
              />
            </>
          ) : null}

          {companionAvailability === "ready" &&
          effectiveCaptureChoice === "undecided" ? (
            <CaptureChoicePanel
              interaction={interaction}
              recordingEnabled={recordingEnabled}
              onChoose={chooseCapture}
            />
          ) : null}

          {companionAvailability === "ready" &&
          effectiveCaptureChoice === "recording" &&
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
                liveNotes={liveNotes}
                onLiveNotesChange={updateLiveNotes}
                onSaveLiveNotes={() => void personalWorkspace.save()}
                liveNotesSaveDisabled={
                  personalWorkspace.loading ||
                  !personalWorkspace.workspace ||
                  personalWorkspace.saveState === "saving"
                }
                liveNotesStatus={liveNotesStatus}
                showLiveNotes={false}
                onElapsedSecondsChange={(seconds) => {
                  elapsedSecondsRef.current = seconds;
                }}
                onActivityChange={handleRecordingActivityChange}
                onFinalized={handleRecordingFinalized}
              />
            </div>
          ) : null}

          {companionAvailability === "ready" &&
          effectiveCaptureChoice === "passive" ? (
            <section className="mt-5 rounded-3xl border border-brand-secondary/25 bg-brand-secondary/10 p-5">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
                Passive Companion
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                No recording or listening
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-700">
                {interaction.interactionType === "phone_call"
                  ? "This browser cannot reliably record the same phone call, so no recording or listening has started."
                  : interaction.interactionType === "online_meeting"
                    ? "You chose not to capture this meeting, so no recording or listening has started."
                    : "Add a photo or marker only when it is safe and appropriate. Markers contain a type and timestamp, never a note."}
              </p>
            </section>
          ) : null}

          {companionAvailability === "ready" &&
          effectiveCaptureChoice !== "undecided" ? (
            <CompanionControls
              markers={markers}
              markersAvailable={markersAvailable}
              markerWritesDisabled={working || markersNeedRefresh}
              visualEnabled={visualEnabled}
              showMarkers={showMarkers}
              onToggleMarkers={() => setShowMarkers((value) => !value)}
              onToggleVisuals={() => setShowVisuals((value) => !value)}
              onAddMarker={(type) => void addMarker(type)}
              onDeleteMarker={(marker) => void deleteMarker(marker)}
              onEnd={() =>
                void endInteraction(
                  interaction.interactionType === "phone_call"
                    ? "connected"
                    : undefined,
                )
              }
              endLabel={endLabel}
              endDisabled={endDisabled}
            />
          ) : null}

          {companionAvailability === "ready" &&
          interaction.interactionType === "phone_call" ? (
            <div className="mt-3 flex flex-wrap gap-3">
              <button
                type="button"
                className="secondary-button"
                disabled={working}
                onClick={() => void endInteraction("no_answer")}
              >
                No answer
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={working}
                onClick={() => void endInteraction("voicemail")}
              >
                Left voicemail
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={working}
                onClick={() => void endInteraction("cancelled")}
              >
                Cancel call
              </button>
            </div>
          ) : null}

          {companionAvailability === "ready" && showVisuals && visualEnabled ? (
            <div className="mt-5" id="companion-visuals">
              <VisualEvidenceCapture
                interactionId={interactionId}
                interactionType={interaction.interactionType}
                lifecycleStatus={interaction.lifecycleStatus}
              />
            </div>
          ) : null}
        </>
      ) : embedded ? (
        <section className="form-card mt-5">
          <h2 className="text-lg font-semibold">Conversation ended</h2>
          <p className="mt-2 text-sm text-brand-muted">
            Open Review & follow-up for your notes, summary and next steps.
          </p>
          {onOpenReview ? (
            <button
              type="button"
              className="primary-button mt-4"
              onClick={onOpenReview}
            >
              Open Review & follow-up
            </button>
          ) : null}
        </section>
      ) : (
        <AfterPhase
          interaction={interaction}
          latestRecording={latestRecording}
          markerCount={markers.length}
          visualCount={visualCount}
          visualEnabled={visualEnabled}
          debriefEnabled={capabilities?.featureFlags.aiDebrief === true}
          showVisuals={showVisuals}
          onToggleVisuals={() => setShowVisuals((value) => !value)}
        />
      )}

      {!embedded && phase === "AFTER" && showVisuals && visualEnabled ? (
        <div className="mt-5">
          <VisualEvidenceCapture
            interactionId={interactionId}
            interactionType={interaction.interactionType}
            lifecycleStatus={interaction.lifecycleStatus}
          />
        </div>
      ) : null}
      {!embedded &&
      phase === "AFTER" &&
      interaction.interactionType === "online_meeting" &&
      capabilities?.featureFlags.onlineMeetingCapture === true ? (
        <div className="mt-5" id="online-meeting-capture">
          <OnlineMeetingCapture interaction={interaction} />
        </div>
      ) : null}
      {!embedded &&
      phase === "AFTER" &&
      capabilities?.featureFlags.aiDebrief === true ? (
        <div className="mt-5" id="companion-debrief">
          <PostInteractionCapture
            interactionId={interactionId}
            interactionType={interaction.interactionType}
            workspaceController={personalWorkspace}
          />
        </div>
      ) : null}
      {companionAvailability === "ready" &&
      capabilities?.featureFlags.liveInteractionIntelligence === true ? (
        <LiveInteractionIntelligence
          interactionId={interactionId}
          interactionInProgress={phase === "DURING"}
          interactionCompleted={phase === "AFTER"}
        />
      ) : null}
    </div>
  );
}

function CompanionAvailabilityNotice({
  availability,
}: {
  availability: Exclude<CompanionAvailability, "ready">;
}) {
  const checking = availability === "checking";
  return (
    <section className="form-card mt-5" aria-live="polite">
      <h2 className="text-lg font-semibold text-slate-950">
        {checking
          ? "Checking optional Companion controls…"
          : "Private notes are still available"}
      </h2>
      {!checking ? (
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {availability === "disabled"
            ? "Companion controls are not enabled for this workspace. You can keep and save private notes without them."
            : "Optional Companion controls are temporarily unavailable. You can keep and save private notes without them."}
        </p>
      ) : null}
    </section>
  );
}

function CoreBeforeControls({
  interaction,
  working,
  onStart,
}: {
  interaction: Interaction;
  working: boolean;
  onStart(): void;
}) {
  return (
    <section className="form-card mt-5">
      <h2 className="text-lg font-semibold text-slate-950">
        Conversation controls
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Starting the conversation remains available without optional guidance,
        capture or marker tools.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          className="primary-button min-h-12"
          disabled={working}
          onClick={onStart}
        >
          {working
            ? "Starting…"
            : interaction.interactionType === "online_meeting"
              ? "Start meeting"
              : interaction.interactionType === "phone_call"
                ? "Start call"
                : "Start interaction"}
        </button>
        {interaction.interactionType === "online_meeting" &&
        interaction.meetingUrl ? (
          <a
            className="secondary-button min-h-12"
            href={interaction.meetingUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open meeting
          </a>
        ) : null}
      </div>
    </section>
  );
}

function CoreDuringControls({
  interaction,
  working,
  endDisabled,
  endLabel,
  onEnd,
}: {
  interaction: Interaction;
  working: boolean;
  endDisabled: boolean;
  endLabel: string;
  onEnd(outcome?: CallOutcome): void;
}) {
  return (
    <section className="form-card mt-5">
      <h2 className="text-lg font-semibold text-slate-950">
        Conversation controls
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Ending the conversation remains available without optional guidance,
        capture or marker tools.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          className="primary-button"
          disabled={endDisabled}
          onClick={() =>
            onEnd(
              interaction.interactionType === "phone_call"
                ? "connected"
                : undefined,
            )
          }
        >
          {endLabel}
        </button>
        {interaction.interactionType === "phone_call" ? (
          <>
            <button
              type="button"
              className="secondary-button"
              disabled={working || endDisabled}
              onClick={() => onEnd("no_answer")}
            >
              No answer
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={working || endDisabled}
              onClick={() => onEnd("voicemail")}
            >
              Left voicemail
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={working || endDisabled}
              onClick={() => onEnd("cancelled")}
            >
              Cancel call
            </button>
          </>
        ) : null}
      </div>
    </section>
  );
}

function BeforePhase({
  interaction,
  brief,
  working,
  onPrepare,
  onStart,
  onOpenPreparation,
}: {
  interaction: Interaction;
  brief: PreInteractionBriefResponse | null;
  working: boolean;
  onPrepare(): void;
  onStart(): void;
  onOpenPreparation?: () => void;
}) {
  const content = brief?.state === "completed" ? brief.brief : null;
  return (
    <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
        30-second brief
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
        <span className="rounded-full bg-brand-secondary/10 px-3 py-1 text-brand-primary">
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
              : interaction.interactionType === "phone_call"
                ? "Start call"
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
        {onOpenPreparation ? (
          <button
            type="button"
            className="secondary-button min-h-14 text-base"
            onClick={onOpenPreparation}
          >
            Open full brief
          </button>
        ) : (
          <Link
            className="secondary-button min-h-14 text-center text-base"
            href={`/conversations/${interaction.id}#preparation`}
          >
            Open full brief
          </Link>
        )}
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
  const browserRecordingExcluded = interaction.interactionType === "phone_call";
  return (
    <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
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
          This browser cannot reliably record the same phone call. No recording
          will start.
        </div>
      ) : null}
      {interaction.interactionType === "online_meeting" ? (
        <p className="mt-4 rounded-xl bg-indigo-50 p-4 text-sm leading-6 text-indigo-950">
          Capture starts only after you choose shared meeting audio plus
          microphone, or microphone only, and confirm participant notice and
          authority. Oryntela never joins the meeting or runs a bot.
        </p>
      ) : null}
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {!browserRecordingExcluded && recordingEnabled ? (
          <button
            type="button"
            className="primary-button min-h-16 text-base"
            onClick={() => onChoose("recording")}
          >
            {interaction.interactionType === "online_meeting"
              ? "Capture meeting audio"
              : "Record interaction"}
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
  markersAvailable,
  markerWritesDisabled,
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
  markersAvailable: boolean;
  markerWritesDisabled: boolean;
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
        {markersAvailable ? (
          <button
            type="button"
            className="secondary-button min-h-16 text-base"
            disabled={markerWritesDisabled}
            onClick={onToggleMarkers}
          >
            Add marker
          </button>
        ) : null}
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
                disabled={markerWritesDisabled}
                className="min-h-14 rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-focus"
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
                  disabled={markerWritesDisabled}
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
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
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
          <a
            className="primary-button min-h-14 text-center text-base"
            href="#companion-debrief"
          >
            Capture what happened
          </a>
        ) : null}
        <Link
          className="secondary-button min-h-14 text-center text-base"
          href={`/conversations/${interaction.id}`}
        >
          Finish
        </Link>
      </div>
      {visualEnabled || interaction.companyId ? (
        <details className="mt-4 rounded-2xl border border-slate-200 p-4">
          <summary className="cursor-pointer font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-focus">
            More options
          </summary>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {visualEnabled ? (
              <button
                type="button"
                className="secondary-button min-h-14 text-base"
                onClick={onToggleVisuals}
              >
                {showVisuals ? "Hide photo capture" : "Add visual evidence"}
              </button>
            ) : null}
            <Link
              className="secondary-button min-h-14 text-center text-base"
              href={
                interaction.companyId
                  ? `/conversations/accounts/${interaction.companyId}`
                  : "/conversations"
              }
            >
              Open conversation history
            </Link>
          </div>
        </details>
      ) : null}
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
