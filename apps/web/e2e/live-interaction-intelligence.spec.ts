import { expect, test } from "@playwright/test";

const interactionId = "interaction-live";

const plannedInteraction = {
  id: interactionId,
  organisationId: "organisation-1",
  companyId: "company-1",
  opportunityId: "opportunity-1",
  contactId: null,
  meetingId: "meeting-live",
  interactionType: "face_to_face_meeting",
  lifecycleStatus: "planned",
  title: "Synthetic expansion review",
  scheduledStartAt: "2026-08-15T01:00:00Z",
  scheduledEndAt: "2026-08-15T02:00:00Z",
  actualStartAt: null,
  actualEndAt: null,
  timezone: "Australia/Sydney",
  creationOrigin: "manual",
  callDirection: null,
  callOutcome: null,
  meetingPlatform: null,
  meetingUrl: null,
  externalMeetingId: null,
  captureSource: null,
  ingestionState: null,
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

const source = {
  transcriptVersionId: "transcript-version-live",
  sequenceStart: 4,
  sequenceEnd: 4,
};

const buyingSignal = {
  id: "signal-buying",
  signalType: "buying_signal",
  statement: "The customer said the team is ready to move forward.",
  lifecycleStatus: "detected",
  provisional: true,
  priority: "high",
  evidenceStrength: "customer_attributed",
  resolutionStatus: "pending",
  source,
  detectedAt: "2026-08-15T01:15:00Z",
  lastUpdatedAt: "2026-08-15T01:15:00Z",
  supersededBy: null,
};

const riskSignal = {
  id: "signal-risk",
  signalType: "risk",
  statement: "Security review may take four weeks.",
  lifecycleStatus: "detected",
  provisional: true,
  priority: "high",
  evidenceStrength: "speaker_uncertain",
  resolutionStatus: "pending",
  source: { ...source, sequenceStart: 5, sequenceEnd: 5 },
  detectedAt: "2026-08-15T01:16:00Z",
  lastUpdatedAt: "2026-08-15T01:16:00Z",
  supersededBy: null,
};

function liveResponse(
  state: "available" | "active" | "completed",
  options: { processed?: boolean; reconciled?: boolean } = {},
) {
  const active = state !== "available";
  const signals = options.processed ? [buyingSignal, riskSignal] : [];
  return {
    availability: "available",
    state,
    safeMessage:
      state === "available"
        ? "An authorised progressive transcript is available. Live Intelligence is optional and provisional."
        : state === "active"
          ? "Live signals are provisional, may change and need post-interaction review."
          : "Final intelligence is authoritative; live signals are retained only for reconciliation.",
    sourceKind: "progressive_transcript",
    sessionId: active ? "live-session-1" : null,
    signals: options.reconciled
      ? [
          {
            ...buyingSignal,
            lifecycleStatus: "promoted_candidate",
            resolutionStatus: "confirmed",
          },
          { ...riskSignal, resolutionStatus: "unsupported" },
        ]
      : signals,
    objectives: active
      ? [
          {
            itemType: "objective",
            itemIndex: 0,
            label: "Agree the rollout plan.",
            progressStatus: options.processed
              ? "possibly_addressed"
              : "unresolved",
          },
        ]
      : [],
    openQuestions: active
      ? [
          {
            itemType: "open_question",
            itemIndex: 0,
            label: "Who owns security approval?",
            progressStatus: "unresolved",
          },
        ]
      : [],
    reconciliation: options.reconciled
      ? { confirmed: 1, revised: 0, unsupported: 1, unresolved: 0 }
      : null,
    generatedAt: options.processed ? "2026-08-15T01:16:00Z" : null,
    updatedAt: "2026-08-15T01:16:00Z",
    nextPollSeconds: 1,
  };
}

test("optional Live Companion progresses and reconciles without exposing raw source data", async ({
  page,
}) => {
  let interaction: Record<string, unknown> = { ...plannedInteraction };
  let live = liveResponse("available");
  let markers: Array<Record<string, unknown>> = [];

  await page.route(
    "http://localhost:8000/api/v1/beta/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          featureFlags: {
            aiCompanion: true,
            aiDebrief: true,
            voiceJournal: true,
            visualEvidence: false,
            recordingCapture: false,
            onlineMeetingCapture: false,
            liveInteractionIntelligence: true,
          },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
  await page.route(
    `http://localhost:8000/api/v1/interactions/${interactionId}**`,
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.endsWith("/companion/brief")) {
        await route.fulfill({ json: completedBrief() });
        return;
      }
      if (path.endsWith("/companion/markers")) {
        if (request.method() === "POST") {
          const marker = {
            id: "marker-live-1",
            interactionId,
            createdByUserId: "user-1",
            markerType: request.postDataJSON().markerType,
            recordingOffsetMs: null,
            createdAt: "2026-08-15T01:17:00Z",
          };
          markers = [marker];
          await route.fulfill({ status: 201, json: marker });
        } else {
          await route.fulfill({ json: markers });
        }
        return;
      }
      if (path.endsWith("/live-intelligence/start")) {
        live = liveResponse("active");
        await route.fulfill({ json: live });
        return;
      }
      if (path.endsWith("/live-intelligence/process")) {
        live = liveResponse("active", { processed: true });
        await route.fulfill({
          json: { ...live, processed: true, newSegmentCount: 2 },
        });
        return;
      }
      if (path.endsWith("/live-intelligence/reconcile")) {
        live = liveResponse("completed", { processed: true, reconciled: true });
        await route.fulfill({ json: { ...live, reconciled: true } });
        return;
      }
      if (path.endsWith("/live-intelligence")) {
        await route.fulfill({ json: live });
        return;
      }
      if (path.endsWith("/start")) {
        interaction = {
          ...interaction,
          lifecycleStatus: "in_progress",
          actualStartAt: "2026-08-15T01:00:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      if (path.endsWith("/complete")) {
        interaction = {
          ...interaction,
          lifecycleStatus: "completed",
          actualEndAt: "2026-08-15T02:00:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      await route.fulfill({ json: interaction });
    },
  );

  await page.goto(`/interactions/${interactionId}/companion`);
  await expect(page.getByText("Live Intelligence is available")).toBeVisible();
  await page.getByRole("button", { name: "Start interaction" }).click();
  await page
    .getByRole("button", { name: "Continue without recording" })
    .click();
  await page.getByRole("button", { name: "Enable Live Intelligence" }).click();

  const companion = page.getByRole("region", { name: "Live Companion" });
  await expect(companion.getByText("Provisional · needs review")).toBeVisible();
  await expect(
    companion.getByText("Agree the rollout plan. — Possibly addressed"),
  ).toBeVisible();
  await expect(companion.getByText("Possible buying signal")).toBeVisible();
  await expect(companion.getByText("Possible risk")).toBeVisible();
  await expect(
    companion.getByText(/speaker identity is uncertain/i),
  ).toBeVisible();

  await page.getByRole("button", { name: "Add marker" }).click();
  await page.getByRole("button", { name: "Important" }).click();
  await expect(page.getByText("Important moment marked.")).toBeVisible();
  await page.getByRole("button", { name: "End interaction" }).click();
  await page
    .getByRole("button", { name: "Compare with final intelligence" })
    .click();
  await expect(
    companion.getByText(
      "1 confirmed · 0 revised · 1 unsupported · 0 unresolved",
    ),
  ).toBeVisible();
  await expect(companion.getByText("Final review: confirmed")).toBeVisible();
  await expect(companion.getByText("Final review: unsupported")).toBeVisible();

  for (const prohibited of [
    "raw transcript",
    "provider request",
    "confidence",
    "deal score",
  ]) {
    await expect(page.getByText(new RegExp(prohibited, "i"))).toHaveCount(0);
  }

  await page.getByRole("button", { name: "Collapse" }).click();
  await expect(
    companion.getByRole("heading", { name: "Emerging" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Show" }).click();
  await expect(
    companion.getByRole("heading", { name: "Emerging" }),
  ).toBeVisible();

  if (process.env.CAPTURE_WO_020_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-020-live-interaction-intelligence.png",
      fullPage: true,
    });
  }

  await page.reload();
  await expect(
    page.getByText("1 confirmed · 0 revised · 1 unsupported · 0 unresolved"),
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
      interactionId,
      interactionType: "face_to_face_meeting",
      briefVersion: 1,
      headline: "Agree a safe rollout path.",
      accountContext: "Synthetic evaluation-stage account.",
      recentChanges: [],
      objectives: [
        {
          objective: "Agree the rollout plan.",
          priority: "high",
          reason: "The date is unresolved.",
        },
      ],
      questionsToAsk: [
        {
          question: "Who owns security approval?",
          purpose: "Clarify ownership.",
          priority: "high",
        },
      ],
      stakeholderFocus: [],
      openCommitments: [],
      risksToWatch: [
        { risk: "Security timing may delay rollout.", severity: "high" },
      ],
      successCriteria: ["A rollout owner and date are agreed."],
      interactionGuidance: "Use the authorised progressive source only.",
      confidence: 0.82,
      companyName: "Synthetic Account",
      opportunityName: "Expansion",
      participants: [],
      nextBestAction: "Confirm the rollout owner.",
    },
  };
}
