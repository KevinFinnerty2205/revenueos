import type { RecordingChunkUpload } from "@revenueos/shared";
import { describe, expect, it } from "vitest";
import { assertRecordingChunkUploadIdentity } from "@/lib/recording-chunk-upload";

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
  ])("rejects a mismatched $field", ({ override }) => {
    expect(() =>
      assertRecordingChunkUploadIdentity({ ...chunk, ...override }, expected),
    ).toThrow("The recording upload could not be verified. Try again.");
  });
});
