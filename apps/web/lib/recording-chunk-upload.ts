import type { RecordingChunkUpload } from "@revenueos/shared";
import { isRecord } from "@/lib/private-response-identity";

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

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isRecordingChunk(value: unknown): value is RecordingChunkCompletion {
  return (
    isRecord(value) &&
    hasIdentifier(value.id) &&
    hasIdentifier(value.recordingSessionId) &&
    typeof value.sequenceNumber === "number" &&
    Number.isInteger(value.sequenceNumber) &&
    value.sequenceNumber >= 0 &&
    value.sequenceNumber <= 9_999 &&
    typeof value.byteSize === "number" &&
    Number.isInteger(value.byteSize) &&
    value.byteSize > 0 &&
    value.byteSize <= 25_000_000 &&
    typeof value.checksumSha256 === "string" &&
    /^[0-9a-f]{64}$/.test(value.checksumSha256) &&
    (value.uploadState === "pending" ||
      value.uploadState === "uploaded" ||
      value.uploadState === "verified" ||
      value.uploadState === "deletion_pending" ||
      value.uploadState === "delete_failed" ||
      value.uploadState === "deleted") &&
    (isTimestamp(value.uploadedAt) ||
      (value.uploadedAt === null && value.uploadState !== "verified")) &&
    isTimestamp(value.createdAt)
  );
}

export function verifyRestoredRecordingChunks(
  value: unknown,
  recordingId: string,
): { verifiedCount: number; lastVerifiedSequence: number | null } {
  if (!Array.isArray(value)) {
    throw new Error("The saved recording chunks could not be verified.");
  }
  const ids = new Set<string>();
  const sequences = new Set<number>();
  let verifiedCount = 0;
  for (const chunk of value) {
    if (
      !isRecordingChunk(chunk) ||
      chunk.recordingSessionId !== recordingId ||
      ids.has(chunk.id) ||
      sequences.has(chunk.sequenceNumber)
    ) {
      throw new Error("The saved recording chunks could not be verified.");
    }
    ids.add(chunk.id);
    sequences.add(chunk.sequenceNumber);
    if (chunk.uploadState === "verified") verifiedCount += 1;
  }
  const contiguous =
    verifiedCount > 0 &&
    verifiedCount === value.length &&
    Array.from({ length: verifiedCount }, (_, index) => index).every((index) =>
      sequences.has(index),
    );

  return {
    verifiedCount,
    lastVerifiedSequence: contiguous ? verifiedCount - 1 : null,
  };
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
