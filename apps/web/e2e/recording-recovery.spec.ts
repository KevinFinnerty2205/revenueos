import { expect, test } from "@playwright/test";
import type {
  Interaction,
  PreInteractionBriefResponse,
  RecordingSession,
  RecordingTranscription,
} from "@revenueos/shared";

const interactionId = "conversation-recording-recovery";
const organisationId = "organisation-recovery";
const ownerUserId = "user-recovery";
const startedAt = "2026-11-18T02:00:00Z";
const stoppedAt = "2026-11-18T02:01:00Z";

test("recovers saved audio from a passive tab while preserving private notes", async ({
  page,
}) => {
  let interaction: Interaction = {
    id: interactionId,
    organisationId,
    title: "Northstar pilot review",
    companyId: null,
    opportunityId: null,
    contactId: null,
    meetingId: null,
    interactionType: "face_to_face_meeting",
    lifecycleStatus: "in_progress",
    scheduledStartAt: null,
    scheduledEndAt: null,
    actualStartAt: startedAt,
    actualEndAt: null,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    callDirection: null,
    callOutcome: null,
    durationSeconds: null,
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    createdByUserId: ownerUserId,
    briefState: "not_generated",
    briefGeneratedAt: null,
    createdAt: startedAt,
    updatedAt: startedAt,
  };
  let recording: RecordingSession = {
    id: "recording-recovery",
    interactionId,
    captureSessionId: "capture-recovery",
    recordingType: "live_audio_recording",
    recordingSource: null,
    lifecycleStatus: "uploading",
    consentState: "acknowledged",
    startedAt,
    stoppedAt,
    durationSeconds: 60,
    expectedMimeType: "audio/webm",
    finalMimeType: null,
    totalBytes: 72,
    chunkCount: 1,
    uploadCompletedAt: null,
    transcriptionStatus: "disabled",
    transcriptionAttempts: 0,
    failureCode: null,
    autoIntelligenceStatus: "disabled",
    sessionExpiresAt: "2099-11-18T03:00:00Z",
    providerMode: "mock",
    externalProcessing: false,
    createdAt: startedAt,
    updatedAt: stoppedAt,
  };
  let workspace = {
    exists: false,
    interactionId,
    organisationId,
    ownerUserId,
    lockVersion: 0,
    liveNotes: "",
    enhancedNotes: "",
    followUpDraft: "",
    followUpReviewed: false,
    generationFingerprint: null,
    generationState: "not_started",
    generationId: null,
    generationTranscriptVersion: null,
    generationPersonalNotesState: "not_included",
    generationFailureCode: null,
    generationRetryAvailable: false,
    generationUpdateAvailable: false,
    generationCompletedAt: null,
    importedFromBrowserAt: null,
    updatedAt: null as string | null,
  };
  const recordingActions: string[] = [];
  let manifestBelongsToRecording = false;

  await page.addInitScript(
    ({ choiceKey }) => {
      sessionStorage.setItem(choiceKey, "passive");
    },
    {
      choiceKey: `revenueos:companion:capture-choice:${organisationId}:${ownerUserId}:${interactionId}`,
    },
  );
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const prefix = `/api/v1/interactions/${interactionId}`;
    if (
      request.method() === "POST" &&
      path.startsWith(`${prefix}/recordings`)
    ) {
      recordingActions.push(path);
    }
    if (path === "/api/v1/me") {
      await route.fulfill({
        json: {
          organisation: { id: organisationId },
          user: { id: ownerUserId },
        },
      });
    } else if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({
        json: { featureFlags: { aiCompanion: true, recordingCapture: true } },
      });
    } else if (path === prefix) {
      await route.fulfill({ json: interaction });
    } else if (path === `${prefix}/companion/brief`) {
      await route.fulfill({
        json: {
          interactionId,
          state: "not_generated",
          generationAvailable: false,
          unavailableReason: null,
          safeMessage: null,
          brief: null,
          generatedAt: null,
          reviewed: false,
          reviewedAt: null,
          priorVersions: [],
          sourceLabels: [],
        } satisfies PreInteractionBriefResponse,
      });
    } else if (path === `${prefix}/companion/markers`) {
      await route.fulfill({ json: [] });
    } else if (path === `${prefix}/personal-workspace`) {
      if (request.method() === "PUT") {
        const { liveNotes } = request.postDataJSON();
        workspace = {
          ...workspace,
          liveNotes,
          exists: true,
          lockVersion: 1,
          updatedAt: stoppedAt,
        };
      }
      await route.fulfill({ json: workspace });
    } else if (path === `${prefix}/recordings`) {
      await route.fulfill({ json: [recording] });
    } else if (path === `${prefix}/recordings/${recording.id}/chunks`) {
      await route.fulfill({
        json: [
          {
            id: "chunk-recovery",
            recordingSessionId: manifestBelongsToRecording
              ? recording.id
              : "different-recording",
            sequenceNumber: 0,
            byteSize: 72,
            checksumSha256: "a".repeat(64),
            uploadState: "verified",
            uploadedAt: stoppedAt,
            createdAt: startedAt,
          },
        ],
      });
    } else if (path === `${prefix}/recordings/${recording.id}/finalize`) {
      expect(request.postDataJSON()).toMatchObject({
        lastSequenceNumber: 0,
        finalMimeType: "audio/webm",
      });
      recording = {
        ...recording,
        lifecycleStatus: "uploaded",
        finalMimeType: "audio/webm",
        uploadCompletedAt: stoppedAt,
      };
      await route.fulfill({ json: recording });
    } else if (path === `${prefix}/recordings/${recording.id}/transcription`) {
      await route.fulfill({
        json: {
          recordingId: recording.id,
          status: "disabled",
          transcriptVersionId: null,
          transcriptId: null,
          meetingId: null,
          version: null,
          source: null,
          language: null,
          text: null,
          segments: [],
          completedAt: null,
          safeMessage: "Transcription is disabled.",
        } satisfies RecordingTranscription,
      });
    } else if (path === `${prefix}/complete`) {
      interaction = {
        ...interaction,
        lifecycleStatus: "completed",
        actualEndAt: stoppedAt,
        durationSeconds: 60,
      };
      await route.fulfill({ json: interaction });
    } else {
      await route.fulfill({
        status: 404,
        json: { code: "not_found", message: "Test fixture has no result." },
      });
    }
  });

  await page.goto(`/conversations/${interactionId}/workspace`);
  const notes = page.getByLabel("Private live notes");
  await notes.fill("Confirm the pilot owner on Friday.");
  const end = page.getByRole("button", {
    name: "Save notes and end interaction",
  });
  const finalise = page.getByRole("button", { name: "Retry finalisation" });
  await expect(
    page.getByText("The saved recording chunks could not be verified."),
  ).toBeVisible();
  await expect(finalise).toBeHidden();
  await expect(end).toBeDisabled();
  expect(recordingActions).toEqual([]);

  manifestBelongsToRecording = true;
  await page.getByRole("button", { name: "Refresh recording status" }).click();
  await expect(finalise).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Recover recording" }),
  ).toBeVisible();
  await expect(
    page.getByText(/The microphone is off in this tab/),
  ).toBeVisible();
  if (process.env.CAPTURE_RECORDING_RECOVERY_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/companion-recording-recovery.png",
      fullPage: true,
      animations: "disabled",
    });
  }
  await finalise.click();
  await expect(end).toBeEnabled();
  await expect(notes).toHaveValue("Confirm the pilot owner on Friday.");
  await end.click();
  await expect(
    page.getByRole("heading", { name: "Conversation ended" }),
  ).toBeVisible();
  expect(workspace.liveNotes).toBe("Confirm the pilot owner on Friday.");
  expect(recordingActions).toEqual([
    `/api/v1/interactions/${interactionId}/recordings/${recording.id}/finalize`,
  ]);
});
