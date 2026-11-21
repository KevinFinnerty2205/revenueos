import type { RecordingChunkUpload } from "@revenueos/shared";

export type RecordingChunkCompletion = Omit<
  RecordingChunkUpload,
  "uploadUrl" | "uploadExpiresAt"
>;

interface RecordingChunkRequestIdentity {
  recordingSessionId: string;
  sequenceNumber: number;
  byteSize: number;
  checksumSha256: string;
}

interface RecordingChunkCompletionIdentity extends RecordingChunkRequestIdentity {
  id: string;
}

function hasIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function assertRecordingChunkUploadIdentity(
  chunk: RecordingChunkUpload,
  expected: RecordingChunkRequestIdentity,
): void {
  if (
    !hasIdentifier(chunk.id) ||
    !hasIdentifier(chunk.uploadUrl) ||
    chunk.recordingSessionId !== expected.recordingSessionId ||
    chunk.sequenceNumber !== expected.sequenceNumber ||
    chunk.byteSize !== expected.byteSize ||
    chunk.checksumSha256 !== expected.checksumSha256 ||
    chunk.uploadState !== "pending"
  ) {
    throw new Error("The recording upload could not be verified. Try again.");
  }
}

export function assertRecordingChunkCompletionIdentity(
  chunk: RecordingChunkCompletion,
  expected: RecordingChunkCompletionIdentity,
): void {
  if (
    chunk.id !== expected.id ||
    chunk.recordingSessionId !== expected.recordingSessionId ||
    chunk.sequenceNumber !== expected.sequenceNumber ||
    chunk.byteSize !== expected.byteSize ||
    chunk.checksumSha256 !== expected.checksumSha256 ||
    chunk.uploadState !== "verified"
  ) {
    throw new Error("The recording upload could not be verified. Try again.");
  }
}
