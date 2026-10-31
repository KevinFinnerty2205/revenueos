"use client";

import type {
  CandidateEvidence,
  DebriefCaptureType,
  DebriefReviewResponse,
  DebriefSession,
  InteractionType,
  MethodologySelectionResponse,
  OpportunityMethodologyResponse,
} from "@revenueos/shared";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { useConversationWorkspace } from "@/lib/use-conversation-workspace";

type InputPreference = "guided" | "voice" | "typed";
type RecordingState = "idle" | "recording" | "paused" | "uploading";
type ReviewDecision = { decision: "accept" | "reject"; statement: string };

const MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/ogg;codecs=opus",
  "audio/webm",
  "audio/mp4",
] as const;

function requestKey(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function storageKey(interactionId: string): string {
  return `revenueos:post-interaction-capture:${interactionId}`;
}

function preferredMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  return MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

function microphoneSupported(): boolean {
  return Boolean(
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof MediaRecorder !== "undefined" &&
    preferredMimeType(),
  );
}

function subscribeToBrowserCapabilities(): () => void {
  return () => undefined;
}

async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  const chunkSize = 32_768;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(
      ...bytes.subarray(offset, offset + chunkSize),
    );
  }
  return btoa(binary);
}

export function PostInteractionCapture({
  interactionId,
  interactionType,
  opportunityId = null,
  restoreLatest = false,
}: {
  interactionId: string;
  interactionType: InteractionType;
  opportunityId?: string | null;
  restoreLatest?: boolean;
}) {
  const [session, setSession] = useState<DebriefSession | null>(null);
  const [preference, setPreference] = useState<InputPreference>("guided");
  const [safetyConfirmed, setSafetyConfirmed] = useState(false);
  const [voiceAcknowledged, setVoiceAcknowledged] = useState(false);
  const [answer, setAnswer] = useState("");
  const [working, setWorking] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, ReviewDecision>>(
    {},
  );
  const [recordingState, setRecordingState] = useState<RecordingState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const microphoneAvailable = useSyncExternalStore(
    subscribeToBrowserCapabilities,
    microphoneSupported,
    () => false,
  );
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordingStartedAtRef = useRef<number | null>(null);
  const recordingCancelledRef = useRef(false);

  const remember = useCallback(
    (next: DebriefSession) => {
      setSession(next);
      if (typeof window !== "undefined") {
        if (
          ["completed", "cancelled", "failed"].includes(next.lifecycleStatus)
        ) {
          window.localStorage.removeItem(storageKey(interactionId));
        } else {
          window.localStorage.setItem(storageKey(interactionId), next.id);
        }
      }
    },
    [interactionId],
  );

  useEffect(() => {
    const saved = window.localStorage.getItem(storageKey(interactionId));
    if (!saved && !restoreLatest) {
      window.queueMicrotask(() => setRestoring(false));
      return;
    }
    const controller = new AbortController();
    apiRequest<DebriefSession | null>(
      saved
        ? `/api/v1/interactions/${interactionId}/debrief/${saved}`
        : `/api/v1/interactions/${interactionId}/debrief/latest`,
      { signal: controller.signal },
    )
      .then((restored) => {
        if (!restored) return;
        remember(restored);
        setVoiceAcknowledged(restored.captureType === "voice_journal");
        if (restored.lifecycleStatus !== "completed") {
          setMessage("Your in-progress capture was restored.");
        }
      })
      .catch(() => window.localStorage.removeItem(storageKey(interactionId)))
      .finally(() => {
        if (!controller.signal.aborted) setRestoring(false);
      });
    return () => controller.abort();
  }, [interactionId, remember, restoreLatest]);

  useEffect(() => {
    if (recordingState !== "recording") return;
    const timer = window.setInterval(() => {
      const startedAt = recordingStartedAtRef.current;
      if (startedAt === null) return;
      const elapsed = Math.max(1, Math.floor((Date.now() - startedAt) / 1000));
      setElapsedSeconds(elapsed);
      if (elapsed >= 120) mediaRecorderRef.current?.stop();
    }, 500);
    return () => window.clearInterval(timer);
  }, [recordingState]);

  useEffect(
    () => () => {
      recordingCancelledRef.current = true;
      if (mediaRecorderRef.current?.state !== "inactive") {
        mediaRecorderRef.current?.stop();
      }
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    },
    [],
  );

  async function start(
    captureType: DebriefCaptureType,
    nextPreference: InputPreference,
  ) {
    if (!safetyConfirmed) {
      setError("Confirm that you are safely stopped before starting.");
      return;
    }
    if (nextPreference === "voice" && !voiceAcknowledged) {
      setError(
        "Confirm the voice-processing notice before using Voice Journal.",
      );
      return;
    }
    setWorking(true);
    setError(null);
    setMessage(null);
    try {
      const next = await apiRequest<DebriefSession>(
        `/api/v1/interactions/${interactionId}/debrief`,
        {
          method: "POST",
          body: JSON.stringify({
            captureType,
            safetyConfirmed: true,
            voiceProcessingAcknowledged: voiceAcknowledged,
            idempotencyKey: requestKey("start"),
          }),
        },
      );
      setPreference(nextPreference);
      remember(next);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The capture could not be started.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function submitText() {
    if (!session || !answer.trim()) return;
    setWorking(true);
    setError(null);
    try {
      const next = await apiRequest<DebriefSession>(
        `/api/v1/interactions/${interactionId}/debrief/${session.id}/response`,
        {
          method: "POST",
          body: JSON.stringify({
            answerText: answer.trim(),
            idempotencyKey: requestKey("answer"),
          }),
        },
      );
      setAnswer("");
      remember(next);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The answer could not be saved.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function uploadRecording(
    blob: Blob,
    mimeType: string,
    duration: number,
  ) {
    if (!session) return;
    setRecordingState("uploading");
    setError(null);
    try {
      const next = await apiRequest<DebriefSession>(
        `/api/v1/interactions/${interactionId}/debrief/${session.id}/voice-response`,
        {
          method: "POST",
          body: JSON.stringify({
            audioBase64: await blobToBase64(blob),
            mimeType,
            durationSeconds: Math.min(120, Math.max(1, duration)),
            language: "en-AU",
            idempotencyKey: requestKey("voice"),
          }),
        },
      );
      remember(next);
      setMessage(
        "Voice answer transcribed and saved. The audio was not retained.",
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? `${requestError.message} You can type the answer instead.`
          : "The voice answer could not be transcribed. You can type it instead.",
      );
    } finally {
      chunksRef.current = [];
      setElapsedSeconds(0);
      setRecordingState("idle");
    }
  }

  async function beginRecording() {
    const mimeType = preferredMimeType();
    if (!microphoneAvailable || !mimeType) {
      setError(
        "Voice capture is not supported in this browser. Type your answer instead.",
      );
      return;
    }
    if (!voiceAcknowledged) {
      setError(
        "Confirm the voice-processing notice before using the microphone.",
      );
      return;
    }
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType });
      recordingCancelledRef.current = false;
      chunksRef.current = [];
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      });
      recorder.addEventListener("stop", () => {
        const duration = Math.max(
          1,
          Math.floor(
            (Date.now() - (recordingStartedAtRef.current ?? Date.now())) / 1000,
          ),
        );
        const blob = new Blob(chunksRef.current, { type: mimeType });
        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;
        recordingStartedAtRef.current = null;
        if (recordingCancelledRef.current) {
          recordingCancelledRef.current = false;
          chunksRef.current = [];
          setElapsedSeconds(0);
          setRecordingState("idle");
          return;
        }
        void uploadRecording(blob, mimeType, duration);
      });
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      recordingStartedAtRef.current = Date.now();
      recorder.start(500);
      setElapsedSeconds(1);
      setRecordingState("recording");
    } catch {
      setError(
        "Microphone access was not available. Type your answer instead.",
      );
    }
  }

  function pauseRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder?.state !== "recording") return;
    recorder.pause();
    setRecordingState("paused");
  }

  function resumeRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder?.state !== "paused") return;
    recordingStartedAtRef.current = Date.now() - elapsedSeconds * 1000;
    recorder.resume();
    setRecordingState("recording");
  }

  function stopRecording() {
    if (mediaRecorderRef.current?.state !== "inactive") {
      mediaRecorderRef.current?.stop();
    }
  }

  function cancelRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder) {
      recordingCancelledRef.current = true;
      if (recorder.state !== "inactive") recorder.stop();
    }
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaRecorderRef.current = null;
    mediaStreamRef.current = null;
    chunksRef.current = [];
    recordingStartedAtRef.current = null;
    setElapsedSeconds(0);
    setRecordingState("idle");
    setMessage("Recording cancelled. No audio was uploaded.");
  }

  async function finish() {
    if (!session) return;
    setWorking(true);
    setError(null);
    try {
      const next = await apiRequest<DebriefSession>(
        `/api/v1/interactions/${interactionId}/debrief/${session.id}/finish`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotencyKey: requestKey("finish"),
            finishEarly: true,
          }),
        },
      );
      remember(next);
      setDecisions(
        Object.fromEntries(
          next.candidates.map((candidate) => [
            candidate.id,
            { decision: "accept", statement: candidate.statement },
          ]),
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The captured evidence could not be prepared for review.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function completeReview() {
    if (!session || decisionsReady(session.candidates, decisions) === false)
      return;
    setWorking(true);
    setError(null);
    try {
      const next = await apiRequest<DebriefReviewResponse>(
        `/api/v1/interactions/${interactionId}/debrief/${session.id}/review`,
        {
          method: "POST",
          body: JSON.stringify({
            decisions: session.candidates.map((candidate) => ({
              candidateId: candidate.id,
              decision: decisions[candidate.id].decision,
              ...(decisions[candidate.id].decision === "accept" &&
              decisions[candidate.id].statement !== candidate.originalStatement
                ? { statement: decisions[candidate.id].statement }
                : {}),
            })),
            idempotencyKey: requestKey("review"),
          }),
        },
      );
      remember(next);
      setMessage(
        next.revenueBrainUpdated
          ? "Reviewed evidence saved to the interaction and Revenue Brain."
          : interactionType === "phone_call" && !next.interactionUpdated
            ? "Your notes were saved. A call that did not connect does not create customer Interaction Intelligence."
            : "Review completed. Rejected items were not added to intelligence.",
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The review could not be completed.",
      );
    } finally {
      setWorking(false);
    }
  }

  if (restoring) {
    return <p role="status">Restoring post-interaction capture…</p>;
  }

  return (
    <section aria-labelledby="post-interaction-title" className="form-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
            Personal notes · preserved separately
          </p>
          <h2
            id="post-interaction-title"
            className="mt-2 text-2xl font-semibold text-slate-950"
          >
            {interactionType === "phone_call"
              ? "Write what you noticed on this call"
              : interactionType === "online_meeting"
                ? "Write what you noticed in this meeting"
                : "Write what changed while it is fresh"}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {interactionType === "phone_call"
              ? "Your original notes and answers are preserved even if later processing fails. Oryntela did not record or monitor the call."
              : interactionType === "online_meeting"
                ? "Your original notes and answers are preserved even if later processing fails. Oryntela did not join, record or monitor the meeting."
                : `Your notes for this ${humanise(interactionType).toLowerCase()} stay separate from enhanced notes. You review any evidence before it is added to shared intelligence.`}
          </p>
        </div>
        {session ? (
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
            {humanise(session.lifecycleStatus)}
          </span>
        ) : null}
      </div>

      {interactionType === "presentation" ? (
        <div className="mt-5 rounded-2xl border border-indigo-200 bg-indigo-50 p-4 text-sm leading-6 text-indigo-950">
          Presentation debriefs focus on audience reactions, customer questions,
          objections, requested material, decision-path changes, commitments and
          the next meeting. Claims from your own deck are not customer buying
          signals.
        </div>
      ) : null}

      {error ? (
        <p
          role="alert"
          className="mt-5 rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
      {message ? (
        <p
          role="status"
          className="mt-5 rounded-xl bg-brand-secondary/10 p-4 text-sm text-brand-primary"
        >
          {message}
        </p>
      ) : null}

      {!session ? (
        <StartCapture
          phoneCall={interactionType === "phone_call"}
          working={working}
          safetyConfirmed={safetyConfirmed}
          voiceAcknowledged={voiceAcknowledged}
          microphoneAvailable={microphoneAvailable}
          onSafetyChange={setSafetyConfirmed}
          onVoiceAcknowledgementChange={setVoiceAcknowledged}
          onStart={(type, nextPreference) => void start(type, nextPreference)}
          onFinishForNow={() =>
            setMessage(
              "Finished for now. You can return to capture this interaction later.",
            )
          }
        />
      ) : null}

      {session?.lifecycleStatus === "collecting" ? (
        <div className="mt-6">
          <div className="rounded-2xl bg-brand-primary p-5 text-white">
            <p className="text-xs font-bold uppercase tracking-[0.15em] text-brand-primary-foreground">
              Question{" "}
              {Math.min(session.turns.length + 1, session.maxQuestions + 1)}
            </p>
            <p className="mt-3 text-xl font-semibold">
              {session.currentQuestion?.status === "ask"
                ? session.currentQuestion.question
                : "You have covered the material points."}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              {session.currentQuestion?.reason}
            </p>
          </div>

          {session.currentQuestion?.status === "ask" ? (
            <div className="mt-5 space-y-4">
              {(preference === "voice" || preference === "guided") &&
              voiceAcknowledged ? (
                <VoiceControls
                  available={microphoneAvailable}
                  state={recordingState}
                  elapsedSeconds={elapsedSeconds}
                  onStart={() => void beginRecording()}
                  onPause={pauseRecording}
                  onResume={resumeRecording}
                  onStop={stopRecording}
                  onCancel={cancelRecording}
                />
              ) : null}
              <label
                className="block text-sm font-semibold text-slate-800"
                htmlFor="debrief-answer"
              >
                {preference === "voice" ? "Or type your answer" : "Your answer"}
              </label>
              <textarea
                id="debrief-answer"
                className="min-h-32 w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-950 focus:border-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-secondary/25"
                maxLength={12_000}
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="Report what changed, what was agreed, and what needs follow-up."
              />
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  className="primary-button"
                  disabled={
                    working || !answer.trim() || recordingState !== "idle"
                  }
                  onClick={() => void submitText()}
                >
                  {working ? "Saving…" : "Save answer"}
                </button>
                {session.canFinish ? (
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={working || recordingState !== "idle"}
                    onClick={() => void finish()}
                  >
                    Finish and review
                  </button>
                ) : null}
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="primary-button mt-5"
              disabled={working}
              onClick={() => void finish()}
            >
              {working ? "Preparing review…" : "Review captured evidence"}
            </button>
          )}

          {session.turns.length ? (
            <details className="mt-6 rounded-2xl border border-slate-200 p-4">
              <summary className="cursor-pointer font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-focus">
                Saved answers ({session.turns.length})
              </summary>
              <ol className="mt-4 space-y-4">
                {session.turns.map((turn) => (
                  <li
                    key={turn.id}
                    className="border-l-2 border-brand-secondary/25 pl-4"
                  >
                    <p className="text-sm font-semibold text-slate-800">
                      {turn.question.question}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-600">
                      {turn.answerText}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Captured by {turn.inputMode}
                    </p>
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
        </div>
      ) : null}

      {session?.lifecycleStatus === "review" ? (
        <EvidenceReview
          candidates={session.candidates}
          decisions={decisions}
          working={working}
          onChange={(candidate, decision) =>
            setDecisions((current) => ({
              ...current,
              [candidate.id]: decision,
            }))
          }
          onComplete={() => void completeReview()}
        />
      ) : null}

      {session?.lifecycleStatus === "completed" ? (
        <CompletedConversationReview
          interactionId={interactionId}
          opportunityId={opportunityId}
          session={session}
        />
      ) : null}
    </section>
  );
}

function CompletedConversationReview({
  interactionId,
  opportunityId,
  session,
}: {
  interactionId: string;
  opportunityId: string | null;
  session: DebriefSession;
}) {
  const accepted = session.candidates.filter(
    (candidate) => candidate.userReviewState === "accepted",
  );
  const initialEnhanced = accepted
    .map((candidate) => `• ${candidate.statement}`)
    .join("\n");
  const actions = accepted.filter((candidate) =>
    ["action_item", "commitment", "next_step"].includes(
      candidate.evidenceCategory,
    ),
  );
  const questions = accepted.filter(
    (candidate) => candidate.evidenceCategory === "open_question",
  );
  const initialFollowUp = [
    "Subject: Conversation follow-up",
    "",
    "Thank you for the conversation. Here is my review draft of what we covered:",
    ...accepted.slice(0, 5).map((candidate) => `- ${candidate.statement}`),
    ...(actions.length
      ? [
          "",
          "Next steps:",
          ...actions.map((candidate) => `- ${candidate.statement}`),
        ]
      : []),
    ...(questions.length
      ? [
          "",
          "Open questions:",
          ...questions.map((candidate) => `- ${candidate.statement}`),
        ]
      : []),
    "",
    "Please correct anything I have misunderstood.",
  ].join("\n");
  const enhancedLegacyKey = `revenueos:enhanced-notes:${interactionId}`;
  const followUpLegacyKey = `revenueos:conversation-follow-up:${interactionId}`;
  const workspace = useConversationWorkspace({
    interactionId,
    initialEnhancedNotes: initialEnhanced,
    initialFollowUpDraft: initialFollowUp,
  });
  const [legacyOwnershipBlocked, setLegacyOwnershipBlocked] = useState(false);

  useEffect(() => {
    let active = true;
    window.queueMicrotask(() => {
      if (active) {
        setLegacyOwnershipBlocked(
          window.localStorage.getItem(enhancedLegacyKey) !== null ||
            window.localStorage.getItem(followUpLegacyKey) !== null,
        );
      }
    });
    return () => {
      active = false;
    };
  }, [enhancedLegacyKey, followUpLegacyKey]);

  return (
    <div className="mt-6 space-y-6">
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
        <h3 className="font-semibold text-emerald-950">Debrief complete</h3>
        <p className="mt-2 text-sm leading-6 text-emerald-900">
          Accepted items remain marked “Reported by you”; they are not treated
          as customer-direct evidence.
        </p>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className="font-semibold text-slate-950">
          Original personal notes
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Preserved separately from enhanced notes. Only the user who captured
          this debrief can retrieve it.
        </p>
        {session.turns.length ? (
          <ol className="mt-4 space-y-4">
            {session.turns.map((turn) => (
              <li key={turn.id} className="border-l-2 border-slate-200 pl-4">
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  {turn.question.question ?? "Personal note"}
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-800">
                  {turn.answerText}
                </p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-4 text-sm text-slate-600">
            No personal notes were saved.
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className="font-semibold text-slate-950">
          Enhanced conversation notes
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Edit the accepted, deterministic debrief output without changing your
          original notes or evidence record.
        </p>
        <textarea
          aria-label="Enhanced conversation notes"
          className="form-control mt-4 min-h-52 py-3"
          disabled={workspace.loading}
          value={workspace.values.enhancedNotes}
          onChange={(event) =>
            workspace.setValues((current) => ({
              ...current,
              enhancedNotes: event.target.value,
            }))
          }
        />
        <button
          type="button"
          className="secondary-button mt-3"
          disabled={workspace.loading || workspace.saveState === "saving"}
          onClick={() => void workspace.save()}
        >
          {workspace.saveState === "saving" ? "Saving…" : "Save enhanced notes"}
        </button>
      </section>

      <StructuredDebrief accepted={accepted} />
      <ConversationFrameworkAssessment
        accepted={accepted}
        opportunityId={opportunityId}
      />

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className="font-semibold text-slate-950">Follow-up draft</h3>
        <p className="mt-2 text-sm leading-6 text-amber-900">
          Advisory draft only. Review before copying or exporting. Oryntela will
          not send it.
        </p>
        <textarea
          aria-label="Follow-up draft"
          className="form-control mt-4 min-h-64 py-3"
          disabled={workspace.loading}
          value={workspace.values.followUpDraft}
          onChange={(event) =>
            workspace.setValues((current) => ({
              ...current,
              followUpDraft: event.target.value,
            }))
          }
        />
        <div className="mt-3 flex flex-wrap gap-3">
          <button
            type="button"
            className="secondary-button"
            disabled={workspace.loading || workspace.saveState === "saving"}
            onClick={() => void workspace.save()}
          >
            Save follow-up draft
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              void navigator.clipboard.writeText(workspace.values.followUpDraft)
            }
          >
            Copy draft
          </button>
        </div>
      </section>
      {legacyOwnershipBlocked ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <p>
            An older browser-only draft exists, but it has no authenticated
            owner metadata. Oryntela will not import or display private content
            that cannot be matched to your user.
          </p>
        </div>
      ) : null}
      {workspace.saveState === "saved" ? (
        <p role="status" className="text-sm font-semibold text-brand-primary">
          Saved privately to your Oryntela workspace. No external action was
          taken.
        </p>
      ) : null}
      {workspace.error ? (
        <div role="alert" className="text-sm font-semibold text-rose-800">
          <p>{workspace.error}</p>
          {workspace.saveState === "conflict" ? (
            <button
              type="button"
              className="secondary-button mt-3"
              onClick={() => void workspace.reload()}
            >
              Reload latest saved draft
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function StructuredDebrief({ accepted }: { accepted: CandidateEvidence[] }) {
  const groups = [
    ["Decisions", ["decision"]],
    ["Objections and competitive context", ["objection", "competitor"]],
    ["Actions and commitments", ["action_item", "commitment", "next_step"]],
    ["Unanswered questions", ["open_question"]],
  ] as const;
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="font-semibold text-slate-950">What was learned</h3>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {groups.map(([title, categories]) => {
          const items = accepted.filter((candidate) =>
            (categories as readonly string[]).includes(
              candidate.evidenceCategory,
            ),
          );
          return (
            <div key={title} className="rounded-xl bg-slate-50 p-4">
              <h4 className="text-sm font-bold text-slate-900">{title}</h4>
              {items.length ? (
                <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-700">
                  {items.map((item) => (
                    <li key={item.id}>{item.statement}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-slate-500">
                  Not discussed or not reported.
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ConversationFrameworkAssessment({
  accepted,
  opportunityId,
}: {
  accepted: CandidateEvidence[];
  opportunityId: string | null;
}) {
  const [selection, setSelection] =
    useState<MethodologySelectionResponse | null>(null);
  const [cumulative, setCumulative] =
    useState<OpportunityMethodologyResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      apiRequest<MethodologySelectionResponse>(
        "/api/v1/methodologies/current",
        {
          signal: controller.signal,
        },
      ),
      opportunityId
        ? apiRequest<OpportunityMethodologyResponse>(
            `/api/v1/opportunities/${opportunityId}/methodology`,
            { signal: controller.signal },
          )
        : Promise.resolve(null),
    ])
      .then(([current, related]) => {
        setSelection(current);
        setCumulative(related);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [opportunityId]);

  const definition = selection?.effectiveDefinition;
  if (!selection || selection.selection === "none" || !definition) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className="font-semibold text-slate-950">Framework assessment</h3>
        <p className="mt-2 text-sm text-slate-600">
          Notes-only mode is selected. Choose BANT, SPICED, MEDDICC or MEDDPICC
          in Frameworks to assess conversation coverage.
        </p>
      </section>
    );
  }
  const fields = definition.fields.map((field) => ({
    ...field,
    evidence: accepted.filter((candidate) =>
      field.evidenceCategories.includes(candidate.evidenceCategory),
    ),
  }));
  const covered = fields.filter((field) => field.evidence.length > 0).length;
  const next = fields.find((field) => field.evidence.length === 0);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="font-semibold text-slate-950">Framework assessment</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        <strong>This conversation:</strong> {covered} of {fields.length}{" "}
        {definition.name} areas have reported evidence. This is coverage, not a
        win probability, and missing areas mean “not discussed”, not a negative
        buyer answer.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {fields.map((field) => (
          <div key={field.key} className="rounded-xl bg-slate-50 p-4">
            <p className="text-sm font-bold text-slate-900">
              {field.displayName}
            </p>
            <p className="mt-1 text-sm text-slate-600">
              {field.evidence.length
                ? `${field.evidence.length} reported evidence item${field.evidence.length === 1 ? "" : "s"}`
                : "Not discussed"}
            </p>
          </div>
        ))}
      </div>
      {next?.suggestedQuestions[0] ? (
        <p className="mt-4 rounded-xl bg-brand-secondary/10 p-4 text-sm text-brand-primary">
          <strong>Suggested next question:</strong> {next.suggestedQuestions[0]}
        </p>
      ) : null}
      <div className="mt-5 border-t border-slate-200 pt-4">
        <p className="text-sm font-bold text-slate-900">
          Cumulative related knowledge
        </p>
        {cumulative?.projection ? (
          <p className="mt-2 text-sm leading-6 text-slate-600">
            The intentionally linked Opportunity has{" "}
            {cumulative.projection.stateCounts.confirmed} confirmed and{" "}
            {cumulative.projection.stateCounts.partiallySupported} partially
            supported areas across related evidence. Open the Opportunity
            workspace for evidence references and reviews.
          </p>
        ) : (
          <p className="mt-2 text-sm leading-6 text-slate-600">
            No cumulative assessment is shown because this conversation is not
            linked to an Opportunity with a generated projection. Oryntela will
            not merge separate initiatives merely because a company matches.
          </p>
        )}
      </div>
    </section>
  );
}

function StartCapture({
  phoneCall,
  working,
  safetyConfirmed,
  voiceAcknowledged,
  microphoneAvailable,
  onSafetyChange,
  onVoiceAcknowledgementChange,
  onStart,
  onFinishForNow,
}: {
  phoneCall: boolean;
  working: boolean;
  safetyConfirmed: boolean;
  voiceAcknowledged: boolean;
  microphoneAvailable: boolean;
  onSafetyChange(value: boolean): void;
  onVoiceAcknowledgementChange(value: boolean): void;
  onStart(type: DebriefCaptureType, preference: InputPreference): void;
  onFinishForNow(): void;
}) {
  return (
    <div className="mt-6 space-y-5">
      <div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950">
        <p className="font-bold">
          Do not use while driving or operating equipment.
        </p>
        <label className="mt-3 flex min-h-11 cursor-pointer items-start gap-3 text-sm leading-6">
          <input
            type="checkbox"
            className="mt-1 h-5 w-5 rounded border-slate-400 text-brand-secondary focus:ring-brand-focus"
            checked={safetyConfirmed}
            onChange={(event) => onSafetyChange(event.target.checked)}
          />
          <span>
            I confirm I am safely stopped and can focus on this debrief.
          </span>
        </label>
      </div>
      <div className="rounded-2xl border border-slate-200 p-4 text-sm leading-6 text-slate-700">
        <div>
          <p className="font-semibold text-slate-950">Start personal notes</p>
          <p className="mt-1">
            Type what you noticed, what was agreed and what needs follow-up.
            Your original wording is preserved and reviewed before intelligence
            is updated.
          </p>
          <button
            type="button"
            className="primary-button mt-4"
            disabled={working || !safetyConfirmed}
            onClick={() => onStart("ai_debrief", "typed")}
          >
            Start personal notes
          </button>
        </div>
      </div>
      <details className="rounded-2xl border border-slate-200 p-4">
        <summary className="cursor-pointer font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-focus">
          Other debrief options
        </summary>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Use a guided debrief or Voice Journal when that better fits the way
          you want to report the interaction.
        </p>
        <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 p-4 text-sm leading-6 text-slate-700">
          <input
            type="checkbox"
            className="mt-1 h-5 w-5 rounded border-slate-400 text-brand-secondary focus:ring-brand-focus"
            checked={voiceAcknowledged}
            onChange={(event) =>
              onVoiceAcknowledgementChange(event.target.checked)
            }
          />
          <span>
            I understand Voice Journal records only my post-interaction report
            and sends each bounded segment for transcription. Oryntela does not
            retain the audio after transcription.
          </span>
        </label>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <StartOption
            title="Start AI Debrief"
            description="A short, guided conversation that asks only the most useful follow-up questions."
            action="Start AI Debrief"
            disabled={working || !safetyConfirmed}
            onClick={() => onStart("ai_debrief", "guided")}
          />
          <StartOption
            title="Add Voice Journal"
            description={
              microphoneAvailable
                ? "Speak a short reflection, pause when needed, then review the transcript."
                : "This browser cannot record audio. You can still type a short journal."
            }
            action={
              microphoneAvailable ? "Start Voice Journal" : "Type a journal"
            }
            disabled={
              working ||
              !safetyConfirmed ||
              (microphoneAvailable && !voiceAcknowledged)
            }
            onClick={() =>
              onStart("voice_journal", microphoneAvailable ? "voice" : "typed")
            }
          />
        </div>
        {phoneCall ? (
          <div className="mt-5 flex flex-wrap gap-3 border-t border-slate-200 pt-5">
            <a className="secondary-button" href="#recording">
              Add Recording
            </a>
            <button
              type="button"
              className="secondary-button"
              onClick={onFinishForNow}
            >
              Finish for now
            </button>
          </div>
        ) : null}
      </details>
    </div>
  );
}

function StartOption({
  title,
  description,
  action,
  disabled,
  onClick,
}: {
  title: string;
  description: string;
  action: string;
  disabled: boolean;
  onClick(): void;
}) {
  return (
    <section className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="font-semibold text-slate-950">{title}</h3>
      <p className="mt-2 flex-1 text-sm leading-6 text-slate-600">
        {description}
      </p>
      <button
        type="button"
        className="secondary-button mt-5"
        disabled={disabled}
        onClick={onClick}
      >
        {action}
      </button>
    </section>
  );
}

function VoiceControls({
  available,
  state,
  elapsedSeconds,
  onStart,
  onPause,
  onResume,
  onStop,
  onCancel,
}: {
  available: boolean;
  state: RecordingState;
  elapsedSeconds: number;
  onStart(): void;
  onPause(): void;
  onResume(): void;
  onStop(): void;
  onCancel(): void;
}) {
  return (
    <div className="rounded-2xl border border-brand-secondary/25 bg-brand-secondary/10 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-brand-primary">Voice answer</p>
          <p className="mt-1 text-sm text-brand-primary">
            Keep this page open. Background and screen-locked recording are not
            supported.
          </p>
        </div>
        {state !== "idle" ? (
          <span
            role="status"
            className="rounded-full bg-white px-3 py-1 text-xs font-bold text-brand-primary"
          >
            {state === "recording" ? "● Recording" : humanise(state)} ·{" "}
            {elapsedSeconds}s / 120s
          </span>
        ) : null}
      </div>
      {!available ? (
        <p
          role="status"
          className="mt-4 text-sm font-semibold text-brand-primary"
        >
          Voice capture is unavailable in this browser. Type your answer below.
        </p>
      ) : (
        <div className="mt-4 flex flex-wrap gap-3">
          {state === "idle" ? (
            <button type="button" className="primary-button" onClick={onStart}>
              Start microphone
            </button>
          ) : null}
          {state === "recording" ? (
            <button
              type="button"
              className="secondary-button"
              onClick={onPause}
            >
              Pause
            </button>
          ) : null}
          {state === "paused" ? (
            <button
              type="button"
              className="secondary-button"
              onClick={onResume}
            >
              Resume
            </button>
          ) : null}
          {state === "recording" || state === "paused" ? (
            <>
              <button type="button" className="primary-button" onClick={onStop}>
                Stop and transcribe
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={onCancel}
              >
                Cancel recording
              </button>
            </>
          ) : null}
          {state === "uploading" ? (
            <p role="status">Transcribing voice answer…</p>
          ) : null}
        </div>
      )}
    </div>
  );
}

function EvidenceReview({
  candidates,
  decisions,
  working,
  onChange,
  onComplete,
}: {
  candidates: CandidateEvidence[];
  decisions: Record<string, ReviewDecision>;
  working: boolean;
  onChange(candidate: CandidateEvidence, decision: ReviewDecision): void;
  onComplete(): void;
}) {
  const ready = decisionsReady(candidates, decisions);
  return (
    <div className="mt-6">
      <div className="rounded-2xl bg-brand-primary p-5 text-white">
        <h3 className="text-xl font-semibold">
          Review before updating intelligence
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          Edit, accept or reject every item. Nothing becomes validated
          intelligence until you finish this review.
        </p>
      </div>
      <div className="mt-5 space-y-4">
        {candidates.map((candidate) => {
          const current = decisions[candidate.id] ?? {
            decision: "accept" as const,
            statement: candidate.statement,
          };
          return (
            <article
              key={candidate.id}
              className="rounded-2xl border border-slate-200 p-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  {humanise(candidate.evidenceCategory)}
                </p>
                <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-800">
                  Reported by you
                </span>
              </div>
              {candidate.conflictState &&
              candidate.conflictState !== "not_assessed" ? (
                <p
                  role={
                    candidate.conflictState === "conflicting"
                      ? "alert"
                      : undefined
                  }
                  className={`mt-3 rounded-xl p-3 text-sm font-semibold ${
                    candidate.conflictState === "conflicting"
                      ? "bg-rose-50 text-rose-900"
                      : candidate.conflictState === "corroborated"
                        ? "bg-emerald-50 text-emerald-900"
                        : "bg-amber-50 text-amber-950"
                  }`}
                >
                  Recording comparison: {humanise(candidate.conflictState)}.
                  {candidate.conflictState === "conflicting"
                    ? " Keep both sources visible and resolve the difference during review."
                    : " The debrief remains salesperson-reported evidence."}
                </p>
              ) : null}
              <label
                className="mt-4 block text-sm font-semibold text-slate-800"
                htmlFor={`candidate-${candidate.id}`}
              >
                Evidence statement
              </label>
              <textarea
                id={`candidate-${candidate.id}`}
                className="mt-2 min-h-24 w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-950 focus:border-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-secondary/25 disabled:bg-slate-100"
                maxLength={1_000}
                disabled={current.decision === "reject"}
                value={current.statement}
                onChange={(event) =>
                  onChange(candidate, {
                    ...current,
                    statement: event.target.value,
                  })
                }
              />
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  className={
                    current.decision === "accept"
                      ? "primary-button"
                      : "secondary-button"
                  }
                  aria-pressed={current.decision === "accept"}
                  onClick={() =>
                    onChange(candidate, {
                      decision: "accept",
                      statement: current.statement,
                    })
                  }
                >
                  Accept
                </button>
                <button
                  type="button"
                  className={
                    current.decision === "reject"
                      ? "primary-button"
                      : "secondary-button"
                  }
                  aria-pressed={current.decision === "reject"}
                  onClick={() =>
                    onChange(candidate, {
                      decision: "reject",
                      statement: current.statement,
                    })
                  }
                >
                  Reject
                </button>
              </div>
            </article>
          );
        })}
      </div>
      <button
        type="button"
        className="primary-button mt-6"
        disabled={!ready || working}
        onClick={onComplete}
      >
        {working ? "Updating…" : "Finish review and update intelligence"}
      </button>
    </div>
  );
}

function decisionsReady(
  candidates: CandidateEvidence[],
  decisions: Record<string, ReviewDecision>,
): boolean {
  return (
    candidates.length > 0 &&
    candidates.every((candidate) => {
      const decision = decisions[candidate.id];
      return Boolean(
        decision &&
        (decision.decision === "reject" || decision.statement.trim()),
      );
    })
  );
}
