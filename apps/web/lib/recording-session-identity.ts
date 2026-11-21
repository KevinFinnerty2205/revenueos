import type {
  RecordingMimeType,
  RecordingSession,
  RecordingSource,
  RecordingType,
} from "@revenueos/shared";

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

function hasIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
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
