import { expect, test } from "@playwright/test";

const baseInteraction = {
  id: "interaction-online",
  organisationId: "organisation-1",
  companyId: "company-1",
  opportunityId: "opportunity-1",
  contactId: null,
  meetingId: "meeting-online",
  interactionType: "online_meeting",
  lifecycleStatus: "planned",
  title: "Teams pilot review",
  scheduledStartAt: "2026-08-15T01:00:00Z",
  scheduledEndAt: "2026-08-15T02:00:00Z",
  actualStartAt: null,
  actualEndAt: null,
  timezone: "Australia/Sydney",
  creationOrigin: "manual",
  callDirection: null,
  callOutcome: null,
  meetingPlatform: "microsoft_teams",
  meetingUrl:
    "https://teams.microsoft.com/l/meetup-join/19%3ameeting_synthetic",
  externalMeetingId: "synthetic-teams-1",
  captureSource: null,
  ingestionState: "not_started",
  durationSeconds: null,
  captureMethods: [],
  intelligenceState: "not_ready",
  recordingAvailable: false,
  createdByUserId: "user-1",
  briefState: "completed",
  briefGeneratedAt: "2026-08-15T00:30:00Z",
  createdAt: "2026-08-15T00:00:00Z",
  updatedAt: "2026-08-15T00:00:00Z",
};

const importedTranscript = {
  id: "online-import-1",
  interactionId: "interaction-online",
  captureSessionId: "capture-online-1",
  meetingId: "meeting-online",
  transcriptVersionId: "version-online-1",
  transcriptId: "transcript-online-1",
  meetingPlatform: "microsoft_teams",
  provenance: "platform_generated",
  sourceFormat: "vtt",
  language: "en-AU",
  version: 1,
  characterCount: 56,
  timestampsPresent: true,
  speakerLabelsPresent: true,
  importedAt: "2026-08-15T02:05:00Z",
  ingestionState: "ready",
  duplicate: false,
  text: "Customer: Security approved\nSeller: Send the pilot plan",
  segments: [
    {
      sequenceNumber: 0,
      startMs: 1000,
      endMs: 3500,
      speakerLabel: "Customer",
      text: "Security approved",
    },
  ],
  safeMessage: "Transcript ready.",
};

test("online meeting uses a safe passive lifecycle and persists transcript import", async ({
  page,
}) => {
  let interaction: Record<string, unknown> = { ...baseInteraction };
  let imported = false;

  await page.route(
    "http://localhost:8000/api/v1/beta/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          featureFlags: {
            openaiProvider: false,
            revenueBrain: true,
            opportunityWorkspace: true,
            aiCompanion: true,
            aiDebrief: true,
            voiceJournal: true,
            visualEvidence: true,
            presentationMode: false,
            recordingCapture: false,
            transcription: false,
            autoGenerateIntelligenceAfterTranscription: false,
            onlineMeetingCapture: true,
            onlineMeetingImport: true,
            onlineMeetingNativeIntegration: false,
            onlineMeetingAutoIngest: false,
            liveInteractionIntelligence: true,
            dataExport: true,
            organisationDeletion: false,
          },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/interactions/interaction-online**",
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.endsWith("/companion/brief")) {
        await route.fulfill({ json: completedBrief() });
        return;
      }
      if (path.endsWith("/companion/markers")) {
        await route.fulfill({ json: [] });
        return;
      }
      if (path.endsWith("/visual-evidence") && request.method() === "GET") {
        await route.fulfill({ json: [] });
        return;
      }
      if (path.endsWith("/start") && request.method() === "POST") {
        interaction = {
          ...interaction,
          lifecycleStatus: "in_progress",
          actualStartAt: "2026-08-15T01:00:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      if (path.endsWith("/complete") && request.method() === "POST") {
        interaction = {
          ...interaction,
          lifecycleStatus: "completed",
          actualEndAt: "2026-08-15T02:00:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      if (path.endsWith("/online-meeting/capabilities")) {
        await route.fulfill({
          json: {
            meetingPlatform: "microsoft_teams",
            recordingImport: false,
            transcriptImport: true,
            nativeFetch: false,
            aiDebrief: true,
            voiceJournal: true,
            nativeConnectionState: "not_configured",
            safeMessage:
              "Authorised recording and transcript imports are available. No meeting-platform connection is configured.",
          },
        });
        return;
      }
      if (path.endsWith("/live-intelligence")) {
        await route.fulfill({
          json: {
            availability: "unavailable",
            state: "unavailable",
            safeMessage:
              "No authorised progressive transcript source is available. Use the post-interaction Debrief instead.",
            sourceKind: null,
            sessionId: null,
            signals: [],
            objectives: [],
            openQuestions: [],
            reconciliation: null,
            generatedAt: null,
            updatedAt: null,
            nextPollSeconds: 15,
          },
        });
        return;
      }
      if (path.endsWith("/online-meeting/transcripts")) {
        await route.fulfill({ json: imported ? [importedTranscript] : [] });
        return;
      }
      if (
        path.endsWith("/online-meeting/transcript") &&
        request.method() === "POST"
      ) {
        expect(request.postDataJSON()).toMatchObject({
          fileName: "pasted-transcript.txt",
          provenance: "platform_generated",
          userAttestedAuthority: true,
          externalProcessingAcknowledged: true,
        });
        imported = true;
        interaction = {
          ...interaction,
          captureSource: "platform_transcript",
          ingestionState: "ready",
          captureMethods: ["transcript"],
        };
        await route.fulfill({ status: 201, json: importedTranscript });
        return;
      }
      await route.fulfill({ json: interaction });
    },
  );

  await page.goto("/interactions/interaction-online");
  const openMeeting = page.getByRole("link", {
    name: "Open meeting",
    exact: true,
  });
  await expect(openMeeting).toHaveAttribute("href", baseInteraction.meetingUrl);
  await expect(openMeeting).toHaveAttribute("target", "_blank");
  await expect(openMeeting).toHaveAttribute("rel", /noopener/);
  await expect(page.getByRole("heading", { name: "Objectives" })).toBeVisible();

  await page.getByRole("button", { name: "Start meeting" }).click();
  await expect(
    page
      .getByRole("region", { name: "Use your meeting platform" })
      .getByText(/remains passive while the meeting runs/i),
  ).toBeVisible();
  await page.getByRole("link", { name: "Continue in Companion" }).click();
  await expect(page.getByText("Live Intelligence unavailable")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /capture meeting audio/i }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "End meeting" }).click();
  const captureMeeting = page.getByRole("region", {
    name: "Capture this meeting",
    exact: true,
  });
  await expect(
    captureMeeting.getByRole("heading", {
      name: "Capture this meeting",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    captureMeeting.getByText("Native fetch: not configured"),
  ).toBeVisible();
  await expect(
    captureMeeting.getByRole("link", { name: "Use AI Debrief" }),
  ).toBeVisible();
  await expect(
    captureMeeting.getByRole("link", { name: "Use Voice Journal" }),
  ).toBeVisible();

  const transcriptImport = page.getByRole("region", {
    name: "Import transcript",
  });
  await transcriptImport
    .getByLabel("Paste transcript text")
    .fill(
      "WEBVTT\n\n00:00:01.000 --> 00:00:03.500\n<v Customer>Security approved",
    );
  await transcriptImport
    .getByRole("checkbox", { name: /authorised to upload/i })
    .check();
  await transcriptImport
    .getByRole("checkbox", { name: /approved processing may send/i })
    .check();
  await transcriptImport
    .getByRole("button", { name: "Import transcript" })
    .click();
  await expect(page.getByText("Transcript ready")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Generate Interaction Intelligence" }),
  ).toHaveAttribute("href", "/meetings/meeting-online");

  if (process.env.CAPTURE_WO_018_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-018-online-meeting-capture.png",
      fullPage: true,
    });
  }

  await page.reload();
  await expect(
    page.getByText("1 authorised transcript version imported."),
  ).toBeVisible();
});

function completedBrief() {
  return {
    state: "completed",
    generationAvailable: true,
    unavailableReason: null,
    safeMessage: null,
    generatedAt: "2026-08-15T00:30:00Z",
    reviewed: true,
    reviewedAt: "2026-08-15T00:35:00Z",
    priorVersions: [],
    sourceLabels: ["Interaction details", "Opportunity record"],
    brief: {
      interactionId: "interaction-online",
      interactionType: "online_meeting",
      briefVersion: 1,
      headline: "Confirm the pilot outcome and security owner.",
      accountContext: "Synthetic evaluation-stage account.",
      recentChanges: [
        {
          change: "Security review moved forward.",
          importance: "high",
          source: "revenue_brain",
        },
      ],
      objectives: [
        {
          objective: "Agree the pilot plan.",
          priority: "high",
          reason: "The next step is unresolved.",
        },
      ],
      questionsToAsk: [
        {
          question: "Who owns the security approval?",
          purpose: "Clarify ownership.",
          priority: "high",
        },
      ],
      stakeholderFocus: [
        { name: "Alex Morgan", role: "champion", focus: "Confirm ownership." },
      ],
      openCommitments: [
        { commitment: "Send the pilot plan.", owner: "Seller", dueDate: null },
      ],
      risksToWatch: [
        { risk: "Security timing may delay the pilot.", severity: "high" },
      ],
      successCriteria: ["A pilot owner and date are agreed."],
      interactionGuidance: "Attend in Teams; RevenueOS remains passive.",
      confidence: 0.82,
      companyName: "Synthetic Account",
      opportunityName: "Pilot",
      participants: [{ name: "Alex Morgan", role: "champion" }],
      nextBestAction: "Confirm the pilot owner.",
    },
  };
}
