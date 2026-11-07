import { expect, test } from "@playwright/test";

test("account history opens one conversation workspace without CRM and preserves notes across sections", async ({
  page,
}, testInfo) => {
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
    if (path === "/api/v1/beta/capabilities")
      return route.fulfill({
        json: {
          featureFlags: {
            aiCompanion: true,
            aiDebrief: false,
            recordingCapture: false,
            visualEvidence: false,
          },
        },
      });
    if (path === "/api/v1/companies/northstar-proof")
      return route.fulfill({
        json: { id: "northstar-proof", name: "Northstar", website: null },
      });
    if (path === "/api/v1/contacts")
      return route.fulfill({
        json: { items: [], total: 0, page: 1, pageSize: 100, pages: 0 },
      });
    if (path === "/api/v1/interactions")
      return route.fulfill({
        json: {
          items: [interaction],
          total: 1,
          page: 1,
          pageSize: 100,
          pages: 1,
        },
      });
    if (path.endsWith("/personal-workspace")) {
      if (request.method() === "PUT")
        workspace = {
          ...workspace,
          ...request.postDataJSON(),
          exists: true,
          lockVersion: workspace.lockVersion + 1,
        };
      return route.fulfill({ json: workspace });
    }
    if (path.endsWith("/companion/brief"))
      return route.fulfill({
        json: {
          state: "not_generated",
          generationAvailable: true,
          brief: null,
          priorVersions: [],
          sourceLabels: [],
          reviewed: false,
        },
      });
    if (path.endsWith("/companion/markers")) return route.fulfill({ json: [] });
    if (path.endsWith("/live-intelligence"))
      return route.fulfill({
        json: {
          state: "disabled",
          availability: "disabled",
          safeMessage:
            "Live transcription is not enabled in this synthetic test.",
        },
      });
    if (path.endsWith("/start"))
      interaction = {
        ...interaction,
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-11-01T02:00:00Z",
      };
    if (path.endsWith("/complete"))
      interaction = {
        ...interaction,
        lifecycleStatus: "completed",
        actualEndAt: "2026-11-01T02:10:00Z",
      };
    if (
      /\/interactions\/conversation-proof(?:\/(?:start|complete))?$/.test(path)
    )
      return route.fulfill({ json: interaction });
    return route.fulfill({
      status: 404,
      json: {
        code: "not_found",
        message: "Not part of this synthetic workflow.",
      },
    });
  });

  await page.goto("/conversations/accounts/northstar-proof");
  await expect(
    page.getByRole("heading", { name: "Northstar", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("CRM details")).toHaveCount(0);
  await expect(
    page.locator(
      'a[href^="/opportunities"], a[href^="/companies"], a[href^="/create"], a[href^="/meetings/"]',
    ),
  ).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath("account-conversations.png"),
    fullPage: true,
  });
  await testInfo.attach("account-conversations", {
    path: testInfo.outputPath("account-conversations.png"),
    contentType: "image/png",
  });
  await page.getByRole("link", { name: /Northstar discovery/ }).click();
  await expect(
    page.getByRole("navigation", { name: "Conversation sections" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Notes & capture", exact: true })
    .click();
  await page.getByRole("button", { name: "Open full brief" }).click();
  await expect(
    page.getByRole("button", { name: "Preparation", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Notes & capture", exact: true })
    .click();
  await page.getByRole("button", { name: "Start interaction" }).click();
  await page
    .getByRole("button", { name: "Continue without recording" })
    .click();
  const notes = page.getByLabel("Private live notes");
  await notes.fill("Ask about the rollout timeline.");
  await page.getByRole("button", { name: "Preparation", exact: true }).click();
  await page
    .getByRole("button", { name: "Notes & capture", exact: true })
    .click();
  await expect(notes).toHaveValue("Ask about the rollout timeline.");
  await page.screenshot({
    path: testInfo.outputPath("conversation-notes-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "End interaction" }).click();
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
  await page.getByRole("button", { name: "Review & follow-up" }).click();
  await expect(
    page.getByRole("heading", { name: "Northstar discovery", exact: true }),
  ).toHaveCount(1);
  expect(requests.some((path) => path.includes("/opportunities"))).toBe(false);
  await page.screenshot({
    path: testInfo.outputPath("conversation-review-desktop.png"),
    fullPage: true,
  });
  await testInfo.attach("conversation-review-desktop", {
    path: testInfo.outputPath("conversation-review-desktop.png"),
    contentType: "image/png",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Notes & capture", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("conversation-review-mobile.png"),
    fullPage: true,
  });
  await testInfo.attach("conversation-review-mobile", {
    path: testInfo.outputPath("conversation-review-mobile.png"),
    contentType: "image/png",
  });
});
