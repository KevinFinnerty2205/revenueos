import { expect, test } from "@playwright/test";

test("account history opens one CRM-independent conversation workspace and preserves private notes across sections", async ({
  page,
}) => {
  const requests: string[] = [];
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
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    callOutcome: null,
    callDirection: null,
    durationSeconds: null,
    briefState: "not_generated",
    createdAt: "2026-11-01T00:00:00Z",
    updatedAt: "2026-11-01T00:00:00Z",
  };
  let workspace = {
    exists: false,
    ownerUserId: "owner-proof",
    lockVersion: 0,
    liveNotes: "",
    enhancedNotes: "",
    followUpDraft: "",
    followUpReviewed: false,
    generationFingerprint: null,
    generationState: "not_available",
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
          name: "Northstar",
          website: null,
          industry: "Facilities",
          location: "Sydney",
        },
      });
      return;
    }
    if (path === "/api/v1/contacts") {
      await route.fulfill({
        json: { items: [], total: 0, page: 1, pageSize: 100, pages: 0 },
      });
      return;
    }
    if (path === "/api/v1/interactions") {
      await route.fulfill({
        json: {
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
    if (path.endsWith("/companion/brief")) {
      await route.fulfill({
        json: {
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

  await page
    .getByRole("button", { name: "Save notes and end interaction" })
    .click();
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
  await expect(
    page.getByRole("heading", { name: "Northstar discovery", exact: true }),
  ).toHaveCount(1);
  expect(requests.some((path) => path.includes("/opportunities"))).toBe(false);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Notes & capture", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
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
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    callOutcome: null,
    callDirection: null,
    durationSeconds: null,
    briefState: "not_generated",
    createdAt: "2026-11-01T00:00:00Z",
    updatedAt: "2026-11-01T00:00:00Z",
  };
  let workspace = {
    exists: false,
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
