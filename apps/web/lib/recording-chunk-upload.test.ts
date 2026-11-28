import type { RecordingChunkUpload } from "@revenueos/shared";
import { describe, expect, it } from "vitest";
import {
  assertRecordingChunkCompletionIdentity,
  assertRecordingChunkUploadIdentity,
  verifyRestoredRecordingChunks,
  type RecordingChunkCompletion,
} from "@/lib/recording-chunk-upload";

const expected = {
  recordingSessionId: "recording-1",
  sequenceNumber: 0,
  byteSize: 32,
  checksumSha256: "a".repeat(64),
};

const chunk: RecordingChunkUpload = {
  id: "chunk-1",
  ...expected,
  uploadState: "pending",
  uploadedAt: null,
  createdAt: "2026-08-15T00:00:00Z",
  uploadUrl: "https://upload.example/chunk-1",
  uploadExpiresAt: "2026-08-15T00:05:00Z",
};

const completedChunk: RecordingChunkCompletion = {
  id: chunk.id,
  recordingSessionId: chunk.recordingSessionId,
  sequenceNumber: chunk.sequenceNumber,
  byteSize: chunk.byteSize,
  checksumSha256: chunk.checksumSha256,
  uploadState: "verified",
  uploadedAt: "2026-08-15T00:01:00Z",
  createdAt: chunk.createdAt,
};

describe("assertRecordingChunkUploadIdentity", () => {
  it("accepts an exact reservation response", () => {
    expect(() =>
      assertRecordingChunkUploadIdentity(chunk, expected),
    ).not.toThrow();
  });

  it.each([
    {
      field: "recording session",
      override: { recordingSessionId: "recording-2" },
    },
    { field: "sequence", override: { sequenceNumber: 1 } },
    { field: "byte size", override: { byteSize: 31 } },
    { field: "checksum", override: { checksumSha256: "b".repeat(64) } },
    { field: "chunk id", override: { id: "" } },
    { field: "upload URL", override: { uploadUrl: "" } },
    { field: "upload state", override: { uploadState: "verified" } },
  ] satisfies Array<{
    field: string;
    override: Partial<RecordingChunkUpload>;
  }>)("rejects a mismatched $field", ({ override }) => {
    expect(() =>
      assertRecordingChunkUploadIdentity({ ...chunk, ...override }, expected),
    ).toThrow("The recording upload could not be verified. Try again.");
  });

  it("accepts an exact verified completion response", () => {
    expect(() =>
      assertRecordingChunkCompletionIdentity(completedChunk, {
        id: chunk.id,
        ...expected,
      }),
    ).not.toThrow();
  });

  it.each([
    { field: "chunk id", override: { id: "chunk-2" } },
    {
      field: "recording session",
      override: { recordingSessionId: "recording-2" },
    },
    { field: "sequence", override: { sequenceNumber: 1 } },
    { field: "byte size", override: { byteSize: 31 } },
    { field: "checksum", override: { checksumSha256: "b".repeat(64) } },
    { field: "upload state", override: { uploadState: "uploaded" } },
  ] satisfies Array<{
    field: string;
    override: Partial<RecordingChunkCompletion>;
  }>)("rejects a completion with mismatched $field", ({ override }) => {
    expect(() =>
      assertRecordingChunkCompletionIdentity(
        { ...completedChunk, ...override },
        { id: chunk.id, ...expected },
      ),
    ).toThrow("The recording upload could not be verified. Try again.");
  });
});

describe("verifyRestoredRecordingChunks", () => {
  const secondChunk = {
    ...completedChunk,
    id: "chunk-2",
    sequenceNumber: 1,
  };

  it("requires a complete contiguous nonempty verified sequence, regardless of response order", () => {
    expect(
      verifyRestoredRecordingChunks(
        [secondChunk, completedChunk],
        expected.recordingSessionId,
      ),
    ).toEqual({ verifiedCount: 2, lastVerifiedSequence: 1 });
    expect(
      verifyRestoredRecordingChunks([], expected.recordingSessionId),
    ).toEqual({ verifiedCount: 0, lastVerifiedSequence: null });
    expect(
      verifyRestoredRecordingChunks([secondChunk], expected.recordingSessionId),
    ).toEqual({ verifiedCount: 1, lastVerifiedSequence: null });
    expect(
      verifyRestoredRecordingChunks(
        [
          completedChunk,
          { ...secondChunk, uploadState: "pending", uploadedAt: null },
        ],
        expected.recordingSessionId,
      ),
    ).toEqual({ verifiedCount: 1, lastVerifiedSequence: null });
  });

  it.each([
    { ...secondChunk, recordingSessionId: "another-recording" },
    { ...secondChunk, id: completedChunk.id },
    { ...secondChunk, sequenceNumber: completedChunk.sequenceNumber },
    { ...secondChunk, byteSize: 0 },
    { ...secondChunk, checksumSha256: undefined },
    { ...secondChunk, uploadState: "finalised" },
    { ...secondChunk, uploadedAt: null },
  ])("rejects a wholly unverified response", (invalidChunk) => {
    expect(() =>
      verifyRestoredRecordingChunks(
        [completedChunk, invalidChunk],
        expected.recordingSessionId,
      ),
    ).toThrow("The saved recording chunks could not be verified.");
  });
});
