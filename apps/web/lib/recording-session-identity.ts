import type {
  RecordingMimeType,
  RecordingSession,
  RecordingSource,
  RecordingTranscription,
  RecordingType,
} from "@revenueos/shared";
import { isRecord } from "@/lib/private-response-identity";

export const RECORDING_SESSION_IDENTITY_ERROR =
  "The recording response did not match this interaction. Try again.";

export type RecordingSessionIdentity = Pick<
  RecordingSession,
  | "id"
  | "interactionId"
  | "captureSessionId"
  | "recordingType"
  | "recordingSource"
  | "expectedMimeType"
>;

interface RequestedRecordingIdentity {
  interactionId: string;
  recordingType: RecordingType;
  recordingSource: RecordingSource | null;
  expectedMimeType: RecordingMimeType;
}

type FinalMimeState = "not_finalised" | "finalised" | "either";

export class RecordingSessionIdentityError extends Error {
  constructor() {
    super(RECORDING_SESSION_IDENTITY_ERROR);
    this.name = "RecordingSessionIdentityError";
  }
}

export function isUnfinishedBrowserRecording(
  recording: RecordingSession,
  now = Date.now(),
): boolean {
  return (
    recording.recordingType === "live_audio_recording" &&
    ["created", "recording", "uploading"].includes(recording.lifecycleStatus) &&
    Date.parse(recording.sessionExpiresAt) > now
  );
}

function hasIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isDate(value: unknown): boolean {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isCount(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isOneOf(value: unknown, choices: readonly string[]): boolean {
  return typeof value === "string" && choices.includes(value);
}

const recordingMimeTypes = ["audio/webm", "audio/mp4", "audio/m4a"];

function isRecordingSession(value: unknown): value is RecordingSession {
  return (
    isRecord(value) &&
    hasIdentifier(value.id) &&
    hasIdentifier(value.interactionId) &&
    hasIdentifier(value.captureSessionId) &&
    isOneOf(value.recordingType, [
      "live_audio_recording",
      "uploaded_audio_recording",
      "imported_audio_recording",
    ]) &&
    (value.recordingSource === null ||
      isOneOf(value.recordingSource, [
        "customer_call_recording",
        "business_phone_recording",
        "user_uploaded_recording",
        "external_provider_recording",
        "platform_recording",
      ])) &&
    isOneOf(value.lifecycleStatus, [
      "created",
      "recording",
      "uploading",
      "uploaded",
      "transcribing",
      "completed",
      "failed",
      "cancelled",
      "deleting",
      "deleted",
    ]) &&
    value.consentState === "acknowledged" &&
    (value.startedAt === null || isDate(value.startedAt)) &&
    (value.stoppedAt === null || isDate(value.stoppedAt)) &&
    (value.durationSeconds === null || isCount(value.durationSeconds)) &&
    isOneOf(value.expectedMimeType, recordingMimeTypes) &&
    (value.finalMimeType === null ||
      isOneOf(value.finalMimeType, recordingMimeTypes)) &&
    isCount(value.totalBytes) &&
    isCount(value.chunkCount) &&
    (value.uploadCompletedAt === null || isDate(value.uploadCompletedAt)) &&
    isOneOf(value.transcriptionStatus, [
      "disabled",
      "queued",
      "processing",
      "completed",
      "failed",
    ]) &&
    isCount(value.transcriptionAttempts) &&
    (value.failureCode === null || typeof value.failureCode === "string") &&
    isOneOf(value.autoIntelligenceStatus, [
      "disabled",
      "not_requested",
      "requested",
      "failed",
    ]) &&
    isDate(value.sessionExpiresAt) &&
    isOneOf(value.providerMode, ["mock", "openai"]) &&
    typeof value.externalProcessing === "boolean" &&
    isDate(value.createdAt) &&
    isDate(value.updatedAt)
  );
}

function validateInteractionAnchor<T extends RecordingSession>(
  session: T,
  interactionId: string,
): T {
  if (
    !hasIdentifier(session.id) ||
    !hasIdentifier(session.captureSessionId) ||
    session.interactionId !== interactionId ||
    (session.finalMimeType !== null &&
      session.finalMimeType !== session.expectedMimeType)
  ) {
    throw new RecordingSessionIdentityError();
  }
  return session;
}

function validateFinalMime(
  session: RecordingSession,
  state: FinalMimeState,
): void {
  if (
    (state === "not_finalised" && session.finalMimeType !== null) ||
    (state === "finalised" &&
      session.finalMimeType !== session.expectedMimeType)
  ) {
    throw new RecordingSessionIdentityError();
  }
}

export function validateCreatedRecordingSession<T extends RecordingSession>(
  session: T,
  requested: RequestedRecordingIdentity,
): T {
  validateInteractionAnchor(session, requested.interactionId);
  if (
    session.recordingType !== requested.recordingType ||
    session.recordingSource !== requested.recordingSource ||
    session.expectedMimeType !== requested.expectedMimeType
  ) {
    throw new RecordingSessionIdentityError();
  }
  validateFinalMime(session, "not_finalised");
  return session;
}

export function validateRecordingSession<T extends RecordingSession>(
  session: T,
  expected: RecordingSessionIdentity,
  options: { finalMimeState?: FinalMimeState } = {},
): T {
  validateInteractionAnchor(session, expected.interactionId);
  if (
    session.id !== expected.id ||
    session.captureSessionId !== expected.captureSessionId ||
    session.recordingType !== expected.recordingType ||
    session.recordingSource !== expected.recordingSource ||
    session.expectedMimeType !== expected.expectedMimeType
  ) {
    throw new RecordingSessionIdentityError();
  }
  validateFinalMime(session, options.finalMimeState ?? "either");
  return session;
}

export function validateRecordingSessionsForInteraction<
  T extends RecordingSession,
>(sessions: T[], interactionId: string): T[] {
  return sessions.map((session) =>
    validateInteractionAnchor(session, interactionId),
  );
}

export function decodeRecordingSessionForInteraction(
  value: unknown,
  interactionId: string,
  finalMimeState: FinalMimeState = "either",
): RecordingSession {
  if (!isRecordingSession(value)) throw new RecordingSessionIdentityError();
  validateInteractionAnchor(value, interactionId);
  validateFinalMime(value, finalMimeState);
  return value;
}

export function decodeRecordingSessionsForInteraction(
  value: unknown,
  interactionId: string,
): RecordingSession[] {
  if (!Array.isArray(value)) throw new RecordingSessionIdentityError();
  const sessions = value.map((item: unknown) =>
    decodeRecordingSessionForInteraction(item, interactionId),
  );
  if (
    new Set(sessions.map(({ id }) => id)).size !== sessions.length ||
    new Set(sessions.map(({ captureSessionId }) => captureSessionId)).size !==
      sessions.length
  ) {
    throw new RecordingSessionIdentityError();
  }
  return sessions;
}

export function validateRecordingTranscription<
  T extends RecordingTranscription,
>(transcription: T, recordingId: string): T {
  if (
    !hasIdentifier(transcription.recordingId) ||
    transcription.recordingId !== recordingId
  ) {
    throw new RecordingSessionIdentityError();
  }
  return transcription;
}
