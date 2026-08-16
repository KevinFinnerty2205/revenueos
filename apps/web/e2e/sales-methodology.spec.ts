import { expect, test } from "@playwright/test";

const opportunityId = "opportunity-methodology";

function definition(key = "meddpicc", name = "MEDDPICC") {
  const fields = [
    ["economic_buyer", "Economic Buyer"],
    ["paper_process", "Paper Process"],
    ["decision_process", "Decision Process"],
    ["champion", "Champion"],
    ["competition", "Competition"],
  ];
  return {
    id: null,
    key,
    name,
    description: "Understand the current evidence-backed buying path.",
    version: 1,
    standard: true,
    status: "active",
    fieldCount: fields.length,
    fields: fields.map(([fieldKey, displayName], index) => ({
      key: fieldKey,
      displayName,
      explanation: `Understand ${displayName}.`,
      order: index + 1,
      required: true,
      evidenceExpectations: ["Current validated evidence"],
      canonicalFacts: [fieldKey],
      evidenceCategories: ["other"],
      freshnessDays: 90,
      suggestedQuestions: [`What should we confirm about ${displayName}?`],
      stageExpectation: "evaluation",
    })),
    createdAt: null,
  };
}

function methodology() {
  const source = {
    sourceType: "interaction_intelligence",
    sourceId: "source-final-1",
    itemKey: "champion",
    label: "Final synthetic pilot review",
    origin: "customer_direct",
    supportedAt: "2026-08-15T03:00:00Z",
    sourceClassification: "Final validated Interaction Intelligence",
  };
  const item = (
    fieldKey: string,
    displayName: string,
    state: "confirmed" | "partially_supported" | "unknown" | "conflicting",
    conclusion: string | null,
  ) => ({
    fieldKey,
    displayName,
    explanation:
      state === "unknown"
        ? "No current evidence identifies the commercial approver."
        : "Current validated evidence supports this interpretation.",
    required: true,
    state,
    conclusion,
    sources: state === "unknown" ? [] : [source],
    conflicts: state === "conflicting" ? [source] : [],
    lastSupportedAt: state === "unknown" ? null : source.supportedAt,
    freshness: "current",
    suggestedQuestion:
      state === "confirmed"
        ? null
        : "Who ultimately owns commercial approval for this project?",
    stageExpectation: "evaluation",
    reviews: [],
  });
  return {
    state: "current",
    generationAvailable: true,
    needsRefresh: false,
    safeMessage: "Current evidence-backed methodology view.",
    definition: definition(),
    projectionId: "projection-2",
    projection: {
      opportunityId,
      methodologyKey: "meddpicc",
      methodologyName: "MEDDPICC",
      definitionVersion: 1,
      projectionVersion: 2,
      engineVersion: 1,
      stateCounts: {
        confirmed: 2,
        partiallySupported: 1,
        unknown: 1,
        conflicting: 1,
        stale: 0,
      },
      items: [
        item("economic_buyer", "Economic Buyer", "unknown", null),
        item(
          "paper_process",
          "Paper Process",
          "partially_supported",
          "Procurement is involved; the final contracting path is unclear.",
        ),
        item(
          "decision_process",
          "Decision Process",
          "conflicting",
          "Current valid sources disagree.",
        ),
        item(
          "champion",
          "Champion",
          "confirmed",
          "The operations lead remains the internal champion.",
        ),
        item(
          "competition",
          "Competition",
          "confirmed",
          "Another vendor and the status quo are active alternatives.",
        ),
      ],
      generatedAt: "2026-08-15T03:00:00Z",
    },
    generatedAt: "2026-08-15T03:00:00Z",
  };
}

function reviewedMethodology() {
  const current = methodology();
  const reportedSource = {
    sourceType: "evidence",
    sourceId: "evidence-economic-buyer",
    itemKey: "stakeholder",
    label: "Reported by you",
    origin: "salesperson_reported",
    supportedAt: "2026-08-15T05:00:00Z",
    sourceClassification: "Salesperson-reported evidence",
  };
  return {
    ...current,
    projectionId: "projection-3",
    projection: {
      ...current.projection,
      projectionVersion: 3,
      stateCounts: {
        ...current.projection.stateCounts,
        partiallySupported: 2,
        unknown: 0,
      },
      items: current.projection.items.map((item) =>
        item.fieldKey === "economic_buyer"
          ? {
              ...item,
              state: "partially_supported" as const,
              conclusion:
                "You reported that Jordan owns commercial approval; customer confirmation is still needed.",
              explanation:
                "Reviewed salesperson-reported evidence identifies an approver without upgrading it to a customer-direct fact.",
              sources: [reportedSource],
              lastSupportedAt: reportedSource.supportedAt,
            }
          : item,
      ),
      generatedAt: "2026-08-15T05:01:00Z",
    },
    generatedAt: "2026-08-15T05:01:00Z",
  };
}

function methodologyInteraction(overrides: Record<string, unknown> = {}) {
  return {
    id: "interaction-methodology",
    organisationId: "organisation-1",
    companyId: "company-1",
    opportunityId,
    contactId: null,
    meetingId: null,
    interactionType: "phone_call",
    lifecycleStatus: "planned",
    title: "Economic buyer follow-up",
    scheduledStartAt: "2026-08-15T04:00:00Z",
    scheduledEndAt: null,
    actualStartAt: null,
    actualEndAt: null,
    callDirection: "outbound",
    callOutcome: null,
    durationSeconds: null,
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    createdByUserId: "user-1",
    briefState: "completed",
    briefGeneratedAt: "2026-08-15T03:55:00Z",
    createdAt: "2026-08-15T03:30:00Z",
    updatedAt: "2026-08-15T03:55:00Z",
    ...overrides,
  };
}

function methodologyBrief(reviewed: boolean) {
  return {
    state: "completed",
    generationAvailable: true,
    unavailableReason: null,
    safeMessage: null,
    generatedAt: "2026-08-15T03:55:00Z",
    reviewed,
    reviewedAt: reviewed ? "2026-08-15T03:58:00Z" : null,
    priorVersions: [],
    sourceLabels: ["Opportunity record", "Sales methodology gap"],
    brief: {
      interactionId: "interaction-methodology",
      interactionType: "phone_call",
      briefVersion: 1,
      headline: "Use this call to clarify commercial approval.",
      accountContext:
        "The current MEDDPICC view has no reliable economic-buyer evidence.",
      recentChanges: [],
      objectives: [
        {
          objective: "Clarify who owns commercial approval.",
          priority: "high",
          reason: "Economic Buyer remains unknown.",
        },
      ],
      questionsToAsk: [
        {
          question: "Who ultimately owns commercial approval for this project?",
          purpose: "Clarify the most important qualification gap.",
          priority: "high",
        },
      ],
      stakeholderFocus: [],
      openCommitments: [],
      risksToWatch: [],
      successCriteria: [
        "The approval owner and next validation step are clear.",
      ],
      interactionGuidance:
        "Keep this phone call to one concise qualification question.",
      confidence: 0.8,
      companyName: "Southern Cross Operations",
      opportunityName: "Revenue workflow pilot",
      participants: [],
      nextBestAction: "Clarify commercial approval ownership.",
    },
  };
}

function methodologyDebrief(
  lifecycleStatus: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id: "methodology-session",
    interactionId: "interaction-methodology",
    captureType: "ai_debrief",
    lifecycleStatus,
    questionCount: 0,
    maxQuestions: 2,
    currentQuestion: {
      status: "ask",
      question: "Did you establish who owns final commercial approval?",
      reason: "Follow up on the single priority gap from the brief.",
      target: "stakeholder",
      priority: "high",
    },
    canFinish: false,
    finishedEarly: false,
    turns: [],
    candidates: [],
    interactionIntelligenceId: null,
    revenueBrainSnapshotId: null,
    startedAt: "2026-08-15T04:05:00Z",
    updatedAt: "2026-08-15T04:05:00Z",
    completedAt: null,
    ...overrides,
  };
}

function economicBuyerCandidate(overrides: Record<string, unknown> = {}) {
  return {
    id: "candidate-economic-buyer",
    evidenceCategory: "stakeholder",
    statement: "Jordan owns final commercial approval.",
    originalStatement: "Jordan owns final commercial approval.",
    origin: "salesperson_reported",
    sourceLabel: "Reported by you",
    supportClassification: "reported",
    validationState: "unreviewed",
    conflictState: "not_assessed",
    userReviewState: "pending",
    sourceCaptureSessionId: "methodology-session",
    evidenceFragmentId: "fragment-economic-buyer",
    acceptedEvidenceId: null,
    entityReference: null,
    explicitlyReportedAt: null,
    edited: false,
    ...overrides,
  };
}

function workspace() {
  return {
    opportunity: {
      id: opportunityId,
      companyId: "company-1",
      companyName: "Southern Cross Operations",
      name: "Revenue workflow pilot",
      stage: "evaluation",
      status: "open",
      estimatedValue: "125000.00",
      currency: "AUD",
      expectedCloseDate: "2026-09-30",
      ownerUserId: "user-1",
      ownerName: "Alex Morgan",
      description: "Synthetic methodology opportunity.",
      createdAt: "2026-08-01T00:00:00Z",
      updatedAt: "2026-08-15T00:00:00Z",
    },
    methodology: methodology(),
    reasoning: {
      state: "insufficient_history",
      message: "More history is needed.",
      latest: null,
      history: [],
    },
    latestMeeting: null,
    recentMeetings: [],
    intelligence: null,
    reportedIntelligence: null,
    visualIntelligence: null,
    latestInteractionCapture: null,
    intelligenceSectionsAvailable: 0,
    partialData: false,
    generatedAt: "2026-08-15T03:00:00Z",
  };
}

async function routeCommon(page: import("@playwright/test").Page) {
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === `/api/v1/opportunities/${opportunityId}/workspace`) {
      await route.fulfill({ json: workspace() });
      return;
    }
    if (path === "/api/v1/meetings") {
      await route.fulfill({
        json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
      });
      return;
    }
    if (path.endsWith("/actions")) {
      await route.fulfill({ json: { items: [], total: 0 } });
      return;
    }
    if (path === `/api/v1/evidence/opportunities/${opportunityId}`) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === "/api/v1/evidence/capabilities") {
      await route.fulfill({
        json: {
          documentEvidence: true,
          emailEvidence: true,
          supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
          emailProviderImport: false,
          documentProviderImport: false,
          safeMessage: "Deliberate evidence only.",
        },
      });
      return;
    }
    if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({
        json: {
          featureFlags: {
            opportunityWorkspace: true,
            salesMethodology: true,
          },
          noticeVersion: 1,
        },
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { code: "not_found", message: "Synthetic route not found." },
    });
  });
}

test("shows an explainable MEDDPICC deal view on desktop and mobile", async ({
  page,
}) => {
  await routeCommon(page);
  await page.goto(`/opportunities/${opportunityId}`);

  await expect(
    page.getByRole("heading", { name: "Sales Methodology" }),
  ).toBeVisible();
  await expect(
    page.getByText(/without scoring or blocking deal stages/i),
  ).toBeVisible();
  await expect(page.getByText("Economic Buyer")).toBeVisible();
  await expect(
    page
      .getByRole("listitem")
      .filter({ hasText: "Economic Buyer" })
      .getByText("Unknown", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Champion" })).toBeHidden();
  await page.getByRole("button", { name: "View all 5 fields" }).click();
  await expect(page.getByRole("heading", { name: "Champion" })).toBeVisible();
  await page
    .getByText(/Why this state · 1 source/i)
    .last()
    .click();
  await expect(
    page.getByText("Final synthetic pilot review").last(),
  ).toBeVisible();

  if (process.env.CAPTURE_WO_024_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-024-methodology-deal.png",
      fullPage: true,
    });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Sales Methodology" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "View all 5 fields" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Methodology" })).toHaveCount(0);
  if (process.env.CAPTURE_WO_024_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-024-methodology-mobile.png",
      fullPage: true,
    });
  }
});

test("carries an economic-buyer gap through brief, debrief, review and refresh", async ({
  page,
}) => {
  let interaction = methodologyInteraction();
  let briefReviewed = false;
  let evidenceAccepted = false;
  let projectionGenerated = false;

  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (path === `/api/v1/opportunities/${opportunityId}/workspace`) {
      const currentMethodology = projectionGenerated
        ? reviewedMethodology()
        : evidenceAccepted
          ? {
              ...methodology(),
              state: "needs_refresh",
              projectionId: null,
              projection: null,
              needsRefresh: true,
              safeMessage:
                "New reviewed evidence is available. Refresh the methodology view.",
            }
          : methodology();
      await route.fulfill({
        json: { ...workspace(), methodology: currentMethodology },
      });
      return;
    }
    if (
      path === `/api/v1/opportunities/${opportunityId}/methodology/generate` &&
      request.method() === "POST"
    ) {
      projectionGenerated = true;
      await route.fulfill({
        json: { ...reviewedMethodology(), reused: false },
      });
      return;
    }
    if (path === "/api/v1/interactions/interaction-methodology/start") {
      interaction = methodologyInteraction({
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T04:00:00Z",
      });
      await route.fulfill({ json: interaction });
      return;
    }
    if (path === "/api/v1/interactions/interaction-methodology/complete") {
      expect(request.postDataJSON()).toEqual({ callOutcome: "connected" });
      interaction = methodologyInteraction({
        lifecycleStatus: "completed",
        actualStartAt: "2026-08-15T04:00:00Z",
        actualEndAt: "2026-08-15T04:04:00Z",
        callOutcome: "connected",
        durationSeconds: 240,
      });
      await route.fulfill({ json: interaction });
      return;
    }
    if (
      path ===
      "/api/v1/interactions/interaction-methodology/companion/brief/review"
    ) {
      briefReviewed = true;
      await route.fulfill({ json: methodologyBrief(true) });
      return;
    }
    if (
      path === "/api/v1/interactions/interaction-methodology/companion/brief"
    ) {
      await route.fulfill({ json: methodologyBrief(briefReviewed) });
      return;
    }
    if (
      path === "/api/v1/interactions/interaction-methodology/debrief" &&
      request.method() === "POST"
    ) {
      await route.fulfill({
        status: 201,
        json: methodologyDebrief("collecting"),
      });
      return;
    }
    if (path.endsWith("/debrief/methodology-session/response")) {
      await route.fulfill({
        json: methodologyDebrief("collecting", {
          questionCount: 1,
          currentQuestion: {
            status: "complete",
            question: null,
            reason: "The priority gap is ready for review.",
            target: null,
            priority: null,
          },
          canFinish: true,
          turns: [
            {
              id: "turn-economic-buyer",
              turnNumber: 1,
              question: methodologyDebrief("collecting").currentQuestion,
              answerText: "Jordan owns final commercial approval.",
              inputMode: "text",
              createdAt: "2026-08-15T04:06:00Z",
            },
          ],
        }),
      });
      return;
    }
    if (path.endsWith("/debrief/methodology-session/finish")) {
      await route.fulfill({
        json: methodologyDebrief("review", {
          currentQuestion: null,
          candidates: [economicBuyerCandidate()],
        }),
      });
      return;
    }
    if (path.endsWith("/debrief/methodology-session/review")) {
      evidenceAccepted = true;
      await route.fulfill({
        json: methodologyDebrief("completed", {
          currentQuestion: null,
          candidates: [
            economicBuyerCandidate({
              validationState: "verified",
              userReviewState: "accepted",
              acceptedEvidenceId: "evidence-economic-buyer",
              explicitlyReportedAt: "2026-08-15T04:05:00Z",
            }),
          ],
          interactionIntelligenceId: "intelligence-economic-buyer",
          revenueBrainSnapshotId: "brain-economic-buyer",
          completedAt: "2026-08-15T04:07:00Z",
          acceptedCount: 1,
          rejectedCount: 0,
          interactionUpdated: true,
          revenueBrainUpdated: true,
        }),
      });
      return;
    }
    if (
      path === "/api/v1/interactions/interaction-methodology/recordings" &&
      request.method() === "GET"
    ) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === "/api/v1/interactions/interaction-methodology") {
      await route.fulfill({ json: interaction });
      return;
    }
    if (path === "/api/v1/meetings") {
      await route.fulfill({
        json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
      });
      return;
    }
    if (path.endsWith("/actions")) {
      await route.fulfill({ json: { items: [], total: 0 } });
      return;
    }
    if (path === `/api/v1/evidence/opportunities/${opportunityId}`) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === "/api/v1/evidence/capabilities") {
      await route.fulfill({
        json: {
          documentEvidence: true,
          emailEvidence: true,
          supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
          emailProviderImport: false,
          documentProviderImport: false,
          safeMessage: "Deliberate evidence only.",
        },
      });
      return;
    }
    if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({
        json: {
          featureFlags: {
            opportunityWorkspace: true,
            salesMethodology: true,
            aiCompanion: true,
            aiDebrief: true,
            voiceJournal: true,
            recordingCapture: false,
            transcription: false,
          },
          noticeVersion: 1,
        },
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { code: "not_found", message: "Synthetic route not found." },
    });
  });

  await page.goto(`/opportunities/${opportunityId}`);
  await expect(
    page
      .getByRole("listitem")
      .filter({ hasText: "Economic Buyer" })
      .getByText("Unknown", { exact: true }),
  ).toBeVisible();

  await page.goto("/interactions/interaction-methodology");
  await expect(
    page.getByText("Who ultimately owns commercial approval for this project?"),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Keep this phone call to one concise qualification question.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mark as reviewed" }).click();
  await page.getByRole("button", { name: "Start call" }).click();
  await page.getByRole("button", { name: "End connected call" }).click();
  await page.getByRole("checkbox", { name: /safely stopped/i }).check();
  await page.getByRole("button", { name: "Type notes" }).click();
  await expect(
    page.getByText("Did you establish who owns final commercial approval?"),
  ).toBeVisible();
  await page
    .getByLabel("Your answer")
    .fill("Jordan owns final commercial approval.");
  await page.getByRole("button", { name: "Save answer" }).click();
  await page.getByRole("button", { name: "Review captured evidence" }).click();
  await expect(page.getByText("Reported by you")).toBeVisible();
  await page
    .getByRole("button", { name: "Finish review and update intelligence" })
    .click();
  await expect(page.getByText("Debrief complete")).toBeVisible();

  await page.goto(`/opportunities/${opportunityId}`);
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "New reviewed evidence is available" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Refresh evidence" }).click();
  const economicBuyer = page
    .getByRole("listitem")
    .filter({ hasText: "Economic Buyer" });
  await expect(
    economicBuyer.getByText("Partially Supported", { exact: true }),
  ).toBeVisible();
  await expect(
    economicBuyer.getByText(/Jordan owns commercial approval/i),
  ).toBeVisible();
  await economicBuyer.getByText(/Why this state · 1 source/i).click();
  await expect(economicBuyer.getByText("Reported by you")).toBeVisible();
  await expect(
    economicBuyer.locator("span").filter({
      hasText: "Salesperson Reported · Salesperson-reported evidence",
    }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page
      .getByRole("listitem")
      .filter({ hasText: "Economic Buyer" })
      .getByText("Partially Supported", { exact: true }),
  ).toBeVisible();
});

test("admin creates and selects bounded custom methodology without JSON or rules", async ({
  page,
}) => {
  let customCreated = false;
  let customSelected = false;
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/methodologies" && request.method() === "GET") {
      const custom = customCreated
        ? [
            {
              ...definition("custom_mutual", "Mutual plan"),
              id: "custom-1",
              standard: false,
            },
          ]
        : [];
      const customDefinition = custom[0] ?? null;
      await route.fulfill({
        json: {
          standards: [definition("meddpicc", "MEDDPICC")],
          custom,
          current: customSelected
            ? {
                selection: "custom",
                customDefinitionId: "custom-1",
                effectiveDefinition: customDefinition,
                updatedAt: "2026-08-15T04:00:00Z",
              }
            : {
                selection: "none",
                customDefinitionId: null,
                effectiveDefinition: null,
                updatedAt: null,
              },
          customMethodologyLimit: 5,
          fieldLimit: 20,
          executableRulesSupported: false,
        },
      });
      return;
    }
    if (
      path === "/api/v1/methodologies/current" &&
      request.method() === "PATCH"
    ) {
      customSelected = true;
      await route.fulfill({
        json: {
          selection: "custom",
          customDefinitionId: "custom-1",
          effectiveDefinition: {
            ...definition("custom_mutual", "Mutual plan"),
            id: "custom-1",
            standard: false,
          },
          updatedAt: "2026-08-15T04:00:00Z",
        },
      });
      return;
    }
    if (
      path === "/api/v1/methodologies/custom" &&
      request.method() === "POST"
    ) {
      customCreated = true;
      await route.fulfill({
        status: 201,
        json: {
          ...definition("custom_mutual", "Mutual plan"),
          id: "custom-1",
          standard: false,
        },
      });
      return;
    }
    if (path === "/api/v1/beta/admin") {
      await route.fulfill({
        status: 403,
        json: { code: "forbidden", message: "Not required by this path." },
      });
      return;
    }
    if (path === `/api/v1/opportunities/${opportunityId}/workspace`) {
      const customWorkspace = workspace();
      customWorkspace.methodology.definition = {
        ...definition("custom_mutual", "Mutual plan"),
        id: null,
        standard: false,
      };
      customWorkspace.methodology.projection.methodologyKey = "custom_mutual";
      customWorkspace.methodology.projection.methodologyName = "Mutual plan";
      await route.fulfill({ json: customWorkspace });
      return;
    }
    if (path === "/api/v1/meetings") {
      await route.fulfill({
        json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
      });
      return;
    }
    if (path.endsWith("/actions")) {
      await route.fulfill({ json: { items: [], total: 0 } });
      return;
    }
    if (path === `/api/v1/evidence/opportunities/${opportunityId}`) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === "/api/v1/evidence/capabilities") {
      await route.fulfill({
        json: {
          documentEvidence: true,
          emailEvidence: true,
          supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
          emailProviderImport: false,
          documentProviderImport: false,
          safeMessage: "Deliberate evidence only.",
        },
      });
      return;
    }
    if (
      path === "/api/v1/integrations" ||
      path === "/api/v1/integrations/connections"
    ) {
      await route.fulfill({
        status: 404,
        json: { code: "disabled", message: "Simulation disabled." },
      });
      return;
    }
    if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({
        json: {
          featureFlags: {
            opportunityWorkspace: true,
            salesMethodology: true,
          },
          noticeVersion: 1,
        },
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { code: "not_found", message: "Synthetic route not found." },
    });
  });
  await page.goto("/settings");

  await expect(
    page.getByRole("heading", { name: "Custom methodology builder" }),
  ).toBeVisible();
  await page.getByLabel("Name", { exact: true }).fill("Mutual plan");
  await page.getByLabel("Purpose").fill("Understand the jointly agreed path.");
  await page.getByLabel("Display name").fill("Success outcome");
  await page.getByLabel("Stable key").fill("success_outcome");
  await page
    .getByLabel("What this field means")
    .fill("The outcome both teams agree matters.");
  await page
    .getByLabel("Expected evidence")
    .fill("Current customer-direct evidence");
  await page
    .getByLabel("Suggested discovery question")
    .fill("What outcome should we agree together?");
  await page.getByRole("button", { name: "Create methodology" }).click();
  await expect(page.getByText(/Created Mutual plan/i)).toBeVisible();
  await expect(
    page.getByText(/Guided fields only. Executable rules/i),
  ).toBeVisible();
  await expect(page.getByText("Mutual plan · v1")).toBeVisible();
  await page
    .locator("div.rounded-2xl")
    .filter({ hasText: "Mutual plan" })
    .getByRole("button", { name: "Select" })
    .click();
  await expect(
    page.getByText(/Existing evidence and projection history are preserved/i),
  ).toBeVisible();

  await page.goto(`/opportunities/${opportunityId}`);
  await expect(
    page.getByText(/Mutual plan organises current validated evidence/i),
  ).toBeVisible();
  await expect(page.getByText("Economic Buyer")).toBeVisible();
});

test("switching BANT to MEDDPICC keeps the historical evidence-backed view", async ({
  page,
}) => {
  let selected: "bant" | "meddpicc" = "bant";
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/methodologies" && request.method() === "GET") {
      await route.fulfill({
        json: {
          standards: [
            definition("bant", "BANT"),
            definition("meddpicc", "MEDDPICC"),
          ],
          custom: [],
          current: {
            selection: selected,
            customDefinitionId: null,
            effectiveDefinition: definition(selected, selected.toUpperCase()),
            updatedAt: "2026-08-15T04:00:00Z",
          },
          customMethodologyLimit: 5,
          fieldLimit: 20,
          executableRulesSupported: false,
        },
      });
      return;
    }
    if (
      path === "/api/v1/methodologies/current" &&
      request.method() === "PATCH"
    ) {
      selected = "meddpicc";
      await route.fulfill({
        json: {
          selection: selected,
          customDefinitionId: null,
          effectiveDefinition: definition("meddpicc", "MEDDPICC"),
          updatedAt: "2026-08-15T04:00:00Z",
        },
      });
      return;
    }
    if (path === `/api/v1/opportunities/${opportunityId}/workspace`) {
      await route.fulfill({ json: workspace() });
      return;
    }
    if (path === `/api/v1/opportunities/${opportunityId}/methodology/history`) {
      const current = methodology().projection;
      const bant = {
        ...current,
        methodologyKey: "bant",
        methodologyName: "BANT",
        projectionVersion: 1,
      };
      await route.fulfill({
        json: {
          currentProjectionId: "projection-2",
          items: [
            {
              id: "projection-2",
              methodologyKey: "meddpicc",
              methodologyName: "MEDDPICC",
              definitionVersion: 1,
              projectionVersion: 2,
              stateCounts: current.stateCounts,
              generatedAt: current.generatedAt,
              projection: current,
            },
            {
              id: "projection-1",
              methodologyKey: "bant",
              methodologyName: "BANT",
              definitionVersion: 1,
              projectionVersion: 1,
              stateCounts: bant.stateCounts,
              generatedAt: "2026-08-14T03:00:00Z",
              projection: bant,
            },
          ],
        },
      });
      return;
    }
    if (path === "/api/v1/meetings") {
      await route.fulfill({
        json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
      });
      return;
    }
    if (path.endsWith("/actions")) {
      await route.fulfill({ json: { items: [], total: 0 } });
      return;
    }
    if (path === `/api/v1/evidence/opportunities/${opportunityId}`) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === "/api/v1/evidence/capabilities") {
      await route.fulfill({
        json: {
          documentEvidence: true,
          emailEvidence: true,
          supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
          emailProviderImport: false,
          documentProviderImport: false,
          safeMessage: "Deliberate evidence only.",
        },
      });
      return;
    }
    if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({
        json: {
          featureFlags: {
            opportunityWorkspace: true,
            salesMethodology: true,
          },
          noticeVersion: 1,
        },
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { code: "disabled", message: "Not used in this path." },
    });
  });

  await page.goto("/settings");
  const meddpiccCard = page
    .locator("div.rounded-2xl")
    .filter({ hasText: "MEDDPICC" });
  await meddpiccCard.getByRole("button", { name: "Select" }).click();
  await expect(
    page.getByText(/Existing evidence and projection history are preserved/i),
  ).toBeVisible();

  await page.goto(`/opportunities/${opportunityId}`);
  await page.getByText("Methodology history").click();
  await page.getByRole("button", { name: "Load history" }).click();
  await expect(page.getByText(/MEDDPICC · view v2/i)).toBeVisible();
  await expect(page.getByText(/BANT · view v1/i)).toBeVisible();
});
