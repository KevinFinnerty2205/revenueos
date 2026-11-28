import { expect, test } from "@playwright/test";
import type { ConversationWorkspaceResponse } from "@revenueos/shared";

test("account history opens one CRM-independent conversation workspace and preserves private notes across sections", async ({
  page,
}) => {
  const requests: string[] = [];
  const completionResponse = Promise.withResolvers<void>();
  const applyRequests: { generationId: string; expectedLockVersion: number }[] =
    [];
  let interaction = {
    id: "conversation-proof",
    organisationId: "organisation-proof",
    companyId: "northstar-proof",
    opportunityId: null,
    contactId: null,
    meetingId: null,
    title: "Northstar discovery",
    interactionType: "face_to_face_meeting",
    lifecycleStatus: "planned",
    scheduledStartAt: null,
    scheduledEndAt: null,
    actualStartAt: null as string | null,
    actualEndAt: null as string | null,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    createdByUserId: "owner-proof",
    callOutcome: null,
    callDirection: null,
    durationSeconds: null,
    briefState: "not_generated",
    briefGeneratedAt: null,
    createdAt: "2026-11-01T00:00:00Z",
    updatedAt: "2026-11-01T00:00:00Z",
  };
  let workspace: ConversationWorkspaceResponse = {
    exists: false,
    interactionId: "conversation-proof",
    organisationId: "organisation-proof",
    ownerUserId: "owner-proof",
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
  const confirmedThread = {
    id: "thread-expansion-proof",
    organisationId: "organisation-proof",
    companyId: "northstar-proof",
    name: "Northstar expansion",
    status: "active",
    interactionCount: 2,
    lastInteractionAt: "2026-11-01T02:10:00Z",
    lockVersion: 1,
    createdByUserId: "owner-proof",
    updatedByUserId: "owner-proof",
    createdAt: "2026-08-15T02:00:00Z",
    updatedAt: "2026-11-01T02:10:00Z",
  };

  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    requests.push(`${request.method()} ${path}`);

    if (path === "/api/v1/me") {
      await route.fulfill({
        json: {
          organisation: { id: "organisation-proof" },
          user: { id: "owner-proof" },
        },
      });
      return;
    }
    if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({
        json: {
          featureFlags: {
            aiCompanion: true,
            aiDebrief: false,
            recordingCapture: false,
            visualEvidence: false,
            liveInteractionIntelligence: false,
          },
        },
      });
      return;
    }
    if (path === "/api/v1/companies/northstar-proof") {
      await route.fulfill({
        json: {
          id: "northstar-proof",
          organisationId: "organisation-proof",
          name: "Northstar",
          website: null,
          industry: "Facilities",
          location: "Sydney",
          employeeCount: null,
          status: "prospect",
          ownerUserId: "owner-proof",
          archivedAt: null,
          createdAt: "2026-11-01T00:00:00Z",
          updatedAt: "2026-11-01T00:00:00Z",
        },
      });
      return;
    }
    if (path === "/api/v1/contacts") {
      await route.fulfill({
        json: {
          organisationId: "organisation-proof",
          items: [],
          total: 0,
          page: 1,
          pageSize: 100,
          pages: 0,
        },
      });
      return;
    }
    if (
      path === "/api/v1/interactions/conversation-proof/conversation-memory"
    ) {
      await route.fulfill({
        json: {
          organisationId: "organisation-proof",
          state: "not_configured",
          safeMessage:
            "No framework is selected. Earlier conversations in the confirmed initiative remain available.",
          definition: null,
          assignment: {
            interactionId: "conversation-proof",
            thread: confirmedThread,
            lockVersion: 1,
            confirmationKind: "user_confirmed",
            confirmedByUserId: "owner-proof",
            confirmedAt: "2026-11-01T02:10:00Z",
          },
          suggestions: [],
          currentConversation: null,
          confirmedThread: null,
          confirmedInitiativeHistory: {
            items: [
              {
                interactionId: "conversation-earlier-proof",
                title: "Northstar rollout workshop",
                interactionType: "workshop",
                lifecycleStatus: "completed",
                occurredAt: "2026-09-18T02:00:00Z",
              },
            ],
            total: 1,
            truncated: false,
          },
          generatedAt: "2026-11-01T02:10:00Z",
        },
      });
      return;
    }
    if (path === "/api/v1/conversation-threads") {
      await route.fulfill({ json: [confirmedThread] });
      return;
    }
    if (path === "/api/v1/interactions") {
      await route.fulfill({
        json: {
          organisationId: "organisation-proof",
          items: [interaction],
          total: 1,
          page: 1,
          pageSize: 100,
          pages: 1,
        },
      });
      return;
    }
    if (path.endsWith("/personal-workspace")) {
      if (request.method() === "PUT") {
        workspace = {
          ...workspace,
          ...request.postDataJSON(),
          exists: true,
          lockVersion: workspace.lockVersion + 1,
        };
      }
      await route.fulfill({ json: workspace });
      return;
    }
    if (path.endsWith("/personal-workspace/generation/apply")) {
      const body = request.postDataJSON() as (typeof applyRequests)[number];
      applyRequests.push(body);
      if (body.expectedLockVersion !== workspace.lockVersion) {
        await route.fulfill({
          status: 409,
          json: {
            code: "conversation_workspace_conflict",
            message: "This private workspace changed in another session.",
          },
        });
        return;
      }
      expect(body.generationId).toBe(workspace.generationId);
      workspace = {
        ...workspace,
        lockVersion: workspace.lockVersion + 1,
        enhancedNotes: "Decision: agree the rollout owner before Friday.",
        followUpDraft: "Could you confirm who will own the rollout?",
        followUpReviewed: false,
        generationFingerprint: "2".repeat(64),
        generationUpdateAvailable: false,
        updatedAt: "2026-11-01T02:12:00Z",
      };
      await route.fulfill({ json: workspace });
      return;
    }
    if (path.endsWith("/companion/brief")) {
      await route.fulfill({
        json: {
          interactionId: "conversation-proof",
          state: "not_generated",
          generationAvailable: true,
          brief: null,
          priorVersions: [],
          sourceLabels: [],
          reviewed: false,
        },
      });
      return;
    }
    if (path.endsWith("/companion/markers")) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith("/start")) {
      interaction = {
        ...interaction,
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-11-01T02:00:00Z",
      };
      await route.fulfill({ json: interaction });
      return;
    }
    if (path.endsWith("/complete")) {
      await completionResponse.promise;
      interaction = {
        ...interaction,
        lifecycleStatus: "completed",
        actualEndAt: "2026-11-01T02:10:00Z",
      };
      await route.fulfill({ json: interaction });
      return;
    }
    if (
      /\/interactions\/conversation-proof(?:\/(?:start|complete))?$/.test(path)
    ) {
      await route.fulfill({ json: interaction });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { code: "not_found", message: "Not part of this test." },
    });
  });

  await page.goto("/conversations/accounts/northstar-proof");
  await expect(
    page.getByRole("heading", { name: "Northstar", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("CRM details")).toHaveCount(0);
  await expect(
    page.locator(
      'a[href^="/opportunities"], a[href^="/companies"], a[href^="/meetings/"]',
    ),
  ).toHaveCount(0);
  if (process.env.CAPTURE_CONVERSATION_WORKSPACE_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/conversation-first-account.png",
      fullPage: true,
    });
  }

  await page.getByRole("link", { name: /Northstar discovery/ }).click();
  await expect(
    page.getByRole("navigation", { name: "Conversation sections" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Notes & capture", exact: true })
    .click();
  await page.getByRole("button", { name: "Start interaction" }).click();
  await page
    .getByRole("button", { name: "Continue without recording" })
    .click();

  const notes = page.getByLabel("Private live notes");
  await notes.fill("Ask about the rollout timeline.");
  if (process.env.CAPTURE_CONVERSATION_WORKSPACE_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/conversation-first-capture.png",
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Preparation", exact: true }).click();
  await page
    .getByRole("button", { name: "Notes & capture", exact: true })
    .click();
  await expect(notes).toHaveValue("Ask about the rollout timeline.");

  const completionRequest = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().endsWith("/interactions/conversation-proof/complete"),
  );
  try {
    await page
      .getByRole("button", { name: "Save notes and end interaction" })
      .click();
    await completionRequest;
    await expect(notes).toBeDisabled();
    await expect(notes).toHaveValue("Ask about the rollout timeline.");
    if (process.env.CAPTURE_REVIEW_HANDOFF_SCREENSHOT === "1") {
      await page.getByRole("main").screenshot({
        path: "../../docs/07-sprints/assets/conversation-review-handoff.png",
        animations: "disabled",
      });
    }
  } finally {
    completionResponse.resolve();
  }
  await expect(
    page.getByRole("heading", { name: "Conversation ended" }),
  ).toBeVisible();
  expect(workspace.liveNotes).toBe("Ask about the rollout timeline.");
  expect(
    requests.indexOf(
      "PUT /api/v1/interactions/conversation-proof/personal-workspace",
    ),
  ).toBeLessThan(
    requests.indexOf("POST /api/v1/interactions/conversation-proof/complete"),
  );

  await page
    .getByRole("button", { name: "Open Review & follow-up", exact: true })
    .click();
  await expect(page.getByLabel("Your rough notes (original)")).toHaveValue(
    "Ask about the rollout timeline.",
  );
  await expect(
    page.getByText(/No automatic transcript version has been prepared yet/),
  ).toBeVisible();
  workspace = {
    ...workspace,
    generationState: "ready",
    generationId: "generated-review-version-2",
    generationTranscriptVersion: 2,
    generationUpdateAvailable: true,
    generationCompletedAt: "2026-11-01T02:10:00Z",
  };
  await page.getByRole("button", { name: "Check status" }).click();
  const applyVersion = page.getByRole("button", {
    name: "Use generated version 2",
  });
  await expect(applyVersion).toBeEnabled();
  workspace = {
    ...workspace,
    liveNotes: "Another tab confirmed the Friday deadline.",
    lockVersion: workspace.lockVersion + 1,
    updatedAt: "2026-11-01T02:11:00Z",
  };
  await applyVersion.click();
  const loadLatest = page.getByRole("button", {
    name: "Load latest saved draft",
  });
  await expect(loadLatest).toBeVisible();
  await expect(applyVersion).toBeDisabled();
  expect(applyRequests).toEqual([
    { generationId: "generated-review-version-2", expectedLockVersion: 1 },
  ]);
  if (process.env.CAPTURE_REVIEW_HANDOFF_SCREENSHOT === "1") {
    await page
      .getByRole("region", { name: "Private post-conversation draft" })
      .screenshot({
        path: "../../docs/07-sprints/assets/conversation-generated-draft-conflict.png",
        animations: "disabled",
      });
  }
  await loadLatest.click();
  await expect(page.getByLabel("Your rough notes (original)")).toHaveValue(
    "Another tab confirmed the Friday deadline.",
  );
  await expect(applyVersion).toBeEnabled();
  expect(applyRequests).toHaveLength(1);
  await applyVersion.click();
  await expect(page.getByLabel("Private follow-up draft")).toHaveValue(
    "Could you confirm who will own the rollout?",
  );
  expect(applyRequests).toEqual([
    { generationId: "generated-review-version-2", expectedLockVersion: 1 },
    { generationId: "generated-review-version-2", expectedLockVersion: 2 },
  ]);
  await expect(
    page.getByRole("heading", { name: "Northstar discovery", exact: true }),
  ).toHaveCount(1);
  expect(requests.some((path) => path.includes("/opportunities"))).toBe(false);

  await page
    .getByRole("button", { name: "Relationship history", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Earlier conversations in this initiative",
    }),
  ).toBeVisible();
  const earlierConversation = page.getByRole("link", {
    name: "Northstar rollout workshop",
  });
  await expect(earlierConversation).toHaveAttribute(
    "href",
    "/conversations/conversation-earlier-proof",
  );
  await page.getByPlaceholder("For example, APAC renewal programme").focus();
  await page.keyboard.press("Tab");
  await expect(earlierConversation).toBeFocused();
  await expect(page.getByRole("heading", { name: /Cumulative/ })).toHaveCount(
    0,
  );
  if (process.env.CAPTURE_CONVERSATION_WORKSPACE_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/initiative-conversation-history.png",
      fullPage: true,
    });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(earlierConversation).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Notes & capture", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);

  workspace = {
    ...workspace,
    exists: true,
    followUpDraft: "Private CRM-free follow-up ready for review.",
    followUpReviewed: false,
    updatedAt: "2026-11-01T02:15:00Z",
  };
  await page.goto("/conversations/conversation-proof?view=review#follow-up");
  const followUp = page.getByRole("region", {
    name: "Follow-up review",
  });
  await expect(followUp).toBeFocused();
  await expect(followUp).toBeInViewport();
  await expect(page.getByLabel("Private follow-up draft")).toHaveValue(
    "Private CRM-free follow-up ready for review.",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("account history survives unavailable contact enrichment", async ({
  page,
}) => {
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const { pathname } = url;

    if (pathname === "/api/v1/me") {
      await route.fulfill({
        json: {
          organisation: { id: "organisation-proof" },
          user: { id: "owner-proof" },
        },
      });
      return;
    }
    if (pathname === "/api/v1/companies/resilient-account") {
      await route.fulfill({
        json: {
          id: "resilient-account",
          organisationId: "organisation-proof",
          name: "Resilient account",
          website: null,
          industry: null,
          location: "Sydney",
          employeeCount: null,
          status: "prospect",
          ownerUserId: "owner-proof",
          archivedAt: null,
          createdAt: "2026-11-01T00:00:00Z",
          updatedAt: "2026-11-01T00:00:00Z",
        },
      });
      return;
    }
    if (pathname === "/api/v1/interactions") {
      await route.fulfill({
        json: {
          organisationId: "organisation-proof",
          items: [
            {
              id: "resilient-conversation",
              organisationId: "organisation-proof",
              companyId: "resilient-account",
              opportunityId: null,
              contactId: "private-contact-id",
              meetingId: null,
              title: "Resilient account call",
              interactionType: "phone_call",
              lifecycleStatus: "planned",
              scheduledStartAt: "2026-11-25T00:00:00Z",
              scheduledEndAt: null,
              actualStartAt: null,
              actualEndAt: null,
              timezone: "Australia/Sydney",
              creationOrigin: "manual",
              captureMethods: [],
              intelligenceState: "not_ready",
              recordingAvailable: false,
              createdByUserId: "owner-proof",
              callOutcome: null,
              callDirection: "outbound",
              durationSeconds: null,
              briefState: "not_generated",
              briefGeneratedAt: null,
              createdAt: "2026-11-01T00:00:00Z",
              updatedAt: "2026-11-01T00:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          pageSize: 100,
          pages: 1,
        },
      });
      return;
    }
    if (pathname === "/api/v1/contacts" && url.searchParams.has("page")) {
      await route.fulfill({
        json: {
          organisationId: "organisation-proof",
          items: [],
          total: 0,
          page: 1,
          pageSize: 100,
          pages: 0,
        },
      });
      return;
    }
    if (pathname === "/api/v1/contacts") {
      await route.fulfill({
        status: 503,
        json: {
          code: "contact_list_unavailable",
          message: "Private contact list failure details",
        },
      });
      return;
    }
    if (pathname === "/api/v1/contacts/private-contact-id") {
      await route.fulfill({
        status: 404,
        json: {
          code: "contact_not_found",
          message: "Private contact lookup failure details",
        },
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { code: "not_found", message: "Not part of this test." },
    });
  });

  await page.goto("/conversations/accounts/resilient-account");

  await expect(
    page.getByRole("heading", { name: "Resilient account", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Resilient account call" }),
  ).toBeVisible();
  await expect(page.getByText("Linked contact")).toBeVisible();
  await expect(page.getByText(/private-contact-id/)).toHaveCount(0);
  await expect(
    page.getByText(/Private contact .* failure details/),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
});

test("a CRM-free private note saves and reloads when AI Companion is disabled", async ({
  page,
}) => {
  const requests: string[] = [];
  const interaction = {
    id: "private-note-proof",
    organisationId: "organisation-proof",
    companyId: null,
    opportunityId: null,
    contactId: null,
    meetingId: null,
    title: "Conference follow-up notes",
    interactionType: "manual_interaction",
    lifecycleStatus: "planned",
    scheduledStartAt: null,
    scheduledEndAt: null,
    actualStartAt: null,
    actualEndAt: null,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    createdByUserId: "owner-proof",
    callOutcome: null,
    callDirection: null,
    durationSeconds: null,
    briefState: "not_generated",
    briefGeneratedAt: null,
    createdAt: "2026-11-01T00:00:00Z",
    updatedAt: "2026-11-01T00:00:00Z",
  };
  let workspace = {
    exists: false,
    interactionId: "private-note-proof",
    organisationId: "organisation-proof",
    ownerUserId: "owner-proof",
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
    updatedAt: null,
  };

  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    requests.push(`${request.method()} ${path}`);

    if (path === "/api/v1/me") {
      await route.fulfill({
        json: {
          organisation: { id: "organisation-proof" },
          user: { id: "owner-proof" },
        },
      });
      return;
    }
    if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({
        json: {
          featureFlags: {
            aiCompanion: false,
            aiDebrief: false,
            recordingCapture: false,
            visualEvidence: false,
            liveInteractionIntelligence: true,
          },
        },
      });
      return;
    }
    if (path === "/api/v1/interactions/private-note-proof/personal-workspace") {
      if (request.method() === "PUT") {
        workspace = {
          ...workspace,
          ...request.postDataJSON(),
          exists: true,
          lockVersion: workspace.lockVersion + 1,
          updatedAt: "2026-11-01T00:05:00Z",
        };
      }
      await route.fulfill({ json: workspace });
      return;
    }
    if (path === "/api/v1/interactions/private-note-proof") {
      await route.fulfill({ json: interaction });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { code: "not_found", message: "Not part of this test." },
    });
  });

  await page.goto("/conversations/private-note-proof");

  await expect(
    page.getByRole("button", { name: "Notes & capture", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const notes = page.getByLabel("Private live notes");
  await expect(notes).toBeEnabled();
  await expect(notes).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Start interaction" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Record interaction" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Continue without recording" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add marker" })).toHaveCount(0);
  await expect(page.getByText("Checking Live Intelligence…")).toHaveCount(0);

  await notes.fill("Send the operations lead the rollout checklist.");
  await page.getByRole("button", { name: "Save private notes" }).click();
  await expect(
    page.getByText("Private notes saved.", { exact: true }),
  ).toBeVisible();
  expect(workspace.liveNotes).toBe(
    "Send the operations lead the rollout checklist.",
  );
  await page.screenshot({
    path: "../../docs/07-sprints/assets/conversation-resilient-private-notes.png",
    fullPage: true,
  });

  await page.reload();
  await expect(page.getByLabel("Private live notes")).toHaveValue(
    "Send the operations lead the rollout checklist.",
  );

  await page.goto("/interactions/private-note-proof/companion");
  const directNotes = page.getByLabel("Private live notes");
  await expect(directNotes).toHaveValue(
    "Send the operations lead the rollout checklist.",
  );
  await expect(directNotes).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Start interaction" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Record interaction" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Continue without recording" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add marker" })).toHaveCount(0);
  await expect(page.getByText("Checking Live Intelligence…")).toHaveCount(0);
  expect(
    requests.some(
      (request) =>
        request.includes("/companion/brief") ||
        request.includes("/companion/markers") ||
        request.endsWith("/recordings") ||
        request.endsWith("/visual-evidence") ||
        request.includes("/live-intelligence"),
    ),
  ).toBe(false);
});
