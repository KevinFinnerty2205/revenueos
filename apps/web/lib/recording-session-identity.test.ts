import type { RecordingSession } from "@revenueos/shared";
import { describe, expect, it } from "vitest";
import {
  decodeRecordingSessionForInteraction,
  decodeRecordingSessionsForInteraction,
  validateCreatedRecordingSession,
  validateRecordingSession,
  validateRecordingSessionsForInteraction,
  validateRecordingTranscription,
} from "@/lib/recording-session-identity";

const session: RecordingSession = {
  id: "recording-1",
  interactionId: "interaction-1",
  captureSessionId: "capture-1",
  recordingType: "live_audio_recording",
  recordingSource: null,
  lifecycleStatus: "created",
  consentState: "acknowledged",
  startedAt: null,
  stoppedAt: null,
  durationSeconds: null,
  expectedMimeType: "audio/webm",
  finalMimeType: null,
  totalBytes: 0,
  chunkCount: 0,
  uploadCompletedAt: null,
  transcriptionStatus: "disabled",
  transcriptionAttempts: 0,
  failureCode: null,
  autoIntelligenceStatus: "disabled",
  sessionExpiresAt: "2026-08-16T00:00:00Z",
  providerMode: "mock",
  externalProcessing: false,
  createdAt: "2026-08-15T00:00:00Z",
  updatedAt: "2026-08-15T00:00:00Z",
};

describe("recording session identity", () => {
  it("anchors a created session to the requested interaction and capture contract", () => {
    expect(
      validateCreatedRecordingSession(session, {
        interactionId: "interaction-1",
        recordingType: "live_audio_recording",
        recordingSource: null,
        expectedMimeType: "audio/webm",
      }),
    ).toBe(session);
  });

  it.each([
    { field: "recording id", override: { id: "" } },
    { field: "capture id", override: { captureSessionId: "" } },
    { field: "interaction", override: { interactionId: "interaction-2" } },
    {
      field: "recording type",
      override: { recordingType: "imported_audio_recording" },
    },
    {
      field: "recording source",
      override: { recordingSource: "user_uploaded_recording" },
    },
    { field: "expected MIME", override: { expectedMimeType: "audio/mp4" } },
    {
      field: "premature final MIME",
      override: { finalMimeType: "audio/webm" },
    },
  ] satisfies Array<{
    field: string;
    override: Partial<RecordingSession>;
  }>)("rejects a created session with mismatched $field", ({ override }) => {
    expect(() =>
      validateCreatedRecordingSession(
        { ...session, ...override },
        {
          interactionId: "interaction-1",
          recordingType: "live_audio_recording",
          recordingSource: null,
          expectedMimeType: "audio/webm",
        },
      ),
    ).toThrow("The recording response did not match this interaction.");
  });

  it("requires later responses to retain exact session identity and final MIME", () => {
    expect(() =>
      validateRecordingSession(
        {
          ...session,
          lifecycleStatus: "uploaded",
          finalMimeType: "audio/webm",
        },
        session,
        { finalMimeState: "finalised" },
      ),
    ).not.toThrow();
    expect(() =>
      validateRecordingSession(
        { ...session, captureSessionId: "capture-2" },
        session,
      ),
    ).toThrow("The recording response did not match this interaction.");
    expect(() =>
      validateRecordingSession(session, session, {
        finalMimeState: "finalised",
      }),
    ).toThrow("The recording response did not match this interaction.");
  });

  it("rejects a foreign session returned by an interaction-scoped list", () => {
    expect(() =>
      validateRecordingSessionsForInteraction(
        [{ ...session, interactionId: "interaction-2" }],
        "interaction-1",
      ),
    ).toThrow("The recording response did not match this interaction.");
  });

  it("decodes complete sessions and rejects malformed, duplicate or mixed lists atomically", () => {
    expect(
      decodeRecordingSessionsForInteraction([session], "interaction-1"),
    ).toEqual([session]);
    for (const list of [
      { sessions: [session] },
      [session, null],
      [
        session,
        { ...session, id: "recording-2", interactionId: "interaction-2" },
      ],
      [session, { ...session, durationSeconds: 35 }],
      [session, { ...session, id: "recording-2" }],
      [{ ...session, transcriptionStatus: undefined }],
      [{ ...session, durationSeconds: "60" }],
      [{ ...session, createdAt: "2026-08-15T00:00:00" }],
      [{ ...session, finalMimeType: "audio/mp4" }],
    ]) {
      expect(() =>
        decodeRecordingSessionsForInteraction(list, "interaction-1"),
      ).toThrow("The recording response did not match this interaction.");
    }
    expect(() =>
      decodeRecordingSessionForInteraction(
        session,
        "interaction-1",
        "finalised",
      ),
    ).toThrow();
    const finalised = {
      ...session,
      lifecycleStatus: "uploaded",
      finalMimeType: "audio/webm",
    };
    expect(
      decodeRecordingSessionForInteraction(
        finalised,
        "interaction-1",
        "finalised",
      ),
    ).toBe(finalised);
  });

  it("requires a transcription to retain the exact recording identity", () => {
    const transcription = {
      recordingId: "recording-1",
      status: "completed" as const,
      transcriptVersionId: "version-1",
      transcriptId: "transcript-1",
      meetingId: "meeting-1",
      version: 1,
      source: "recorded_audio" as const,
      language: "en-AU",
      text: "Synthetic transcript.",
      segments: [],
      completedAt: "2026-08-15T00:05:00Z",
      safeMessage: "Transcription is ready.",
    };

    expect(validateRecordingTranscription(transcription, "recording-1")).toBe(
      transcription,
    );
    expect(() =>
      validateRecordingTranscription(
        { ...transcription, recordingId: "recording-2" },
        "recording-1",
      ),
    ).toThrow("The recording response did not match this interaction.");
    expect(() =>
      validateRecordingTranscription(
        { ...transcription, recordingId: "" },
        "recording-1",
      ),
    ).toThrow("The recording response did not match this interaction.");
  });
});
