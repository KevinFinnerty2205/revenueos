import type { RecordingChunkUpload } from "@revenueos/shared";

interface RecordingChunkIdentity {
  recordingSessionId: string;
  sequenceNumber: number;
  byteSize: number;
  checksumSha256: string;
}

export function assertRecordingChunkUploadIdentity(
  chunk: RecordingChunkUpload,
  expected: RecordingChunkIdentity,
): void {
  if (
    chunk.recordingSessionId !== expected.recordingSessionId ||
    chunk.sequenceNumber !== expected.sequenceNumber ||
    chunk.byteSize !== expected.byteSize ||
    chunk.checksumSha256 !== expected.checksumSha256
  ) {
    throw new Error("The recording upload could not be verified. Try again.");
  }
}
