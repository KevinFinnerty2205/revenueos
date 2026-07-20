import { expect, test } from "@playwright/test";

test("landing page explains the current product honestly", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "The AI sales teammate that remembers every customer interaction and turns conversations into action.",
    }),
  ).toBeVisible();
  await expect(
    page.getByText(/conversation recording, AI processing/i),
  ).toBeVisible();
});

test("development user can open the protected dashboard shell", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await expect(page.getByText(/mock authentication is active/i)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Today’s Priorities" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
});

test("core entity pages remain usable at a mobile viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/companies");

  await expect(page.getByRole("heading", { name: "Companies" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Create company" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toBeVisible();
});

test("company creation exposes required validation and navigation", async ({
  page,
}) => {
  await page.goto("/companies/new");

  await expect(
    page.getByRole("heading", { name: "Create company" }),
  ).toBeVisible();
  await expect(page.getByLabel(/company name/i)).toHaveAttribute(
    "required",
    "",
  );
  await expect(page.getByRole("link", { name: "Cancel" })).toHaveAttribute(
    "href",
    "/companies",
  );
});

test("meeting list and create form are responsive and deliberate", async ({
  page,
}) => {
  await page.route("http://localhost:8000/api/v1/meetings**", async (route) => {
    await route.fulfill({
      json: {
        items: [
          {
            id: "meeting-1",
            organisationId: "organisation-1",
            title: "Acme discovery",
            description: "Discuss expansion.",
            meetingDate: "2026-08-01T00:00:00Z",
            meetingType: "remote",
            status: "scheduled",
            companyId: "company-1",
            ownerUserId: "user-1",
            createdBy: "user-1",
            updatedBy: "user-1",
            createdAt: "2026-07-17T00:00:00Z",
            updatedAt: "2026-07-17T00:00:00Z",
          },
        ],
        page: 1,
        pageSize: 20,
        total: 1,
        pages: 1,
      },
    });
  });
  await page.route(
    "http://localhost:8000/api/v1/companies**",
    async (route) => {
      await route.fulfill({
        json: {
          items: [{ id: "company-1", name: "Acme Australia" }],
          page: 1,
          pageSize: 100,
          total: 1,
          pages: 1,
        },
      });
    },
  );
  await page.route("http://localhost:8000/api/v1/contacts**", async (route) => {
    await route.fulfill({
      json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/meetings");

  await expect(page.getByRole("heading", { name: "Meetings" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Acme discovery" }),
  ).toBeVisible();
  await expect(
    page.getByRole("article").getByText("Acme Australia"),
  ).toBeVisible();

  await page.getByRole("link", { name: "Create meeting" }).click();
  await expect(
    page.getByRole("heading", { name: "Create meeting" }),
  ).toBeVisible();
  await expect(page.getByLabel("Title")).toHaveAttribute("required", "");
  await expect(page.getByLabel("Meeting date")).toHaveAttribute("required", "");
  await expect(page.getByText(/does not record or transcribe/i)).toBeVisible();
});

test("meeting detail orchestrates and persists the unified Meeting Intelligence workspace", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"], {
    origin: "http://localhost:3000",
  });
  let stage:
    "not_started" | "extractions" | "prerequisites" | "email" | "completed" =
    "not_started";
  let extractionRead = 0;

  await page.route(
    "http://localhost:8000/api/v1/meetings/meeting-1**",
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/participants")) {
        await route.fulfill({ json: [] });
        return;
      }
      if (path.endsWith("/history")) {
        await route.fulfill({ json: [] });
        return;
      }
      if (path.endsWith("/transcript")) {
        await route.fulfill({
          json: {
            id: "transcript-1",
            organisationId: "organisation-1",
            meetingId: "meeting-1",
            rawText:
              "The customer approved the pilot and Alex will send the plan.",
            language: "en-AU",
            version: 1,
            source: "manual",
            createdAt: "2026-07-20T00:00:00Z",
            updatedAt: "2026-07-20T00:00:00Z",
          },
        });
        return;
      }
      if (path.endsWith("/intelligence/generate")) {
        if (stage === "not_started") stage = "extractions";
        else if (stage === "prerequisites") stage = "email";
        await route.fulfill({
          status: 202,
          json: generationWorkspace(stage),
        });
        return;
      }
      if (path.endsWith("/intelligence")) {
        if (stage === "extractions") {
          extractionRead += 1;
          if (extractionRead > 1) stage = "prerequisites";
        } else if (stage === "email") {
          stage = "completed";
        }
        await route.fulfill({ json: workspace(stage) });
        return;
      }
      await route.fulfill({ json: meeting() });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/companies**",
    async (route) => {
      await route.fulfill({
        json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
      });
    },
  );

  await page.goto("/meetings/meeting-1");
  await page.getByRole("tab", { name: "Intelligence" }).click();
  await expect(
    page.getByRole("heading", { name: "Meeting Intelligence" }),
  ).toBeVisible();
  await expect(page.getByText("0 of 6 ready")).toBeVisible();

  await page
    .getByRole("button", { name: "Generate Meeting Intelligence" })
    .click();
  await expect(
    page.getByText(/Generating 5 sections|5 sections queued/),
  ).toBeVisible();
  await expect(page.getByText("6 of 6 ready")).toBeVisible({ timeout: 12_000 });
  await expect(
    page
      .getByRole("article", { name: "Key Decisions" })
      .getByText("Proceed with the pilot.", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Action Items" })
      .getByText("Send the implementation plan.", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Risks & Blockers" })
      .getByText("Security review may delay the pilot."),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Open Questions" })
      .getByText("Who will approve production access?"),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Follow-up Email" })
      .locator("p")
      .filter({ hasText: "Subject: Pilot next steps" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Copy" }).click();
  await expect(page.getByText("Email copied to clipboard.")).toBeVisible();
  await expect(page.getByRole("button", { name: /send/i })).toHaveCount(0);
  if (process.env.CAPTURE_WO_005_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-005-unified-meeting-intelligence.png",
      fullPage: true,
    });
  }

  await page.reload();
  await page.getByRole("tab", { name: "Intelligence" }).click();
  await expect(page.getByText("6 of 6 ready")).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Key Decisions" })
      .getByText("Proceed with the pilot.", { exact: true }),
  ).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  const hasHorizontalOverflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});

function meeting() {
  return {
    id: "meeting-1",
    organisationId: "organisation-1",
    title: "Pilot readiness review",
    description: "Confirm pilot next steps.",
    meetingDate: "2026-07-20T00:00:00Z",
    meetingType: "remote",
    status: "completed",
    companyId: null,
    ownerUserId: "user-1",
    createdBy: "user-1",
    updatedBy: "user-1",
    createdAt: "2026-07-20T00:00:00Z",
    updatedAt: "2026-07-20T00:00:00Z",
  };
}

function capability(state: string, content: object | null = null) {
  return {
    state,
    generationAvailable: state === "not_generated" || state === "failed",
    message: null,
    generatedAt: state === "completed" ? "2026-07-20T00:00:08Z" : null,
    emptyResult: false,
    content,
  };
}

function workspace(
  stage:
    "not_started" | "extractions" | "prerequisites" | "email" | "completed",
) {
  const contentReady =
    stage === "prerequisites" || stage === "email" || stage === "completed";
  const extractionState = contentReady
    ? "completed"
    : stage === "extractions"
      ? "processing"
      : "not_generated";
  const emailState =
    stage === "completed"
      ? "completed"
      : stage === "email"
        ? "queued"
        : "unavailable";
  const ready = stage === "completed" ? 6 : contentReady ? 5 : 0;
  const processing = stage === "extractions" ? 5 : 0;
  const queued = stage === "email" ? 1 : 0;
  return {
    overallState:
      stage === "not_started"
        ? "not_started"
        : stage === "extractions"
          ? "processing"
          : stage === "prerequisites"
            ? "partially_generated"
            : stage === "email"
              ? "queued"
              : "completed",
    generationAvailable: stage === "not_started" || stage === "prerequisites",
    retryAvailable: false,
    lastUpdatedAt: stage === "not_started" ? null : "2026-07-20T00:00:08Z",
    progress: {
      ready,
      queued,
      processing,
      failed: 0,
      notGenerated: 6 - ready - queued - processing,
      total: 6,
      summary:
        stage === "not_started"
          ? "0 of 6 ready"
          : stage === "extractions"
            ? "Generating 5 sections"
            : stage === "prerequisites"
              ? "5 of 6 ready"
              : stage === "email"
                ? "1 section queued"
                : "6 of 6 ready",
    },
    executiveSummary: capability(
      extractionState,
      contentReady
        ? {
            executiveSummary:
              "The customer confirmed the pilot scope and next steps.",
            meetingType: "sales_discovery",
            sentiment: "positive",
            confidence: 0.91,
          }
        : null,
    ),
    decisions: capability(
      extractionState,
      contentReady
        ? {
            decisions: [
              {
                decision: "Proceed with the pilot.",
                owner: "Customer team",
                status: "confirmed",
                confidence: 0.9,
                evidence: "The customer approved the pilot.",
              },
            ],
          }
        : null,
    ),
    actionItems: capability(
      extractionState,
      contentReady
        ? {
            actionItems: [
              {
                task: "Send the implementation plan.",
                owner: "Alex",
                dueDate: "2026-07-30",
                priority: "high",
                status: "open",
                confidence: 0.89,
                evidence: "Alex committed to sending the plan.",
              },
            ],
          }
        : null,
    ),
    risksBlockers: capability(
      extractionState,
      contentReady
        ? {
            risks: [
              {
                risk: "Security review may delay the pilot.",
                category: "security",
                severity: "high",
                owner: "Customer security",
                confidence: 0.84,
                evidence: "The reviewer has not been assigned.",
              },
            ],
          }
        : null,
    ),
    openQuestions: capability(
      extractionState,
      contentReady
        ? {
            openQuestions: [
              {
                question: "Who will approve production access?",
                owner: null,
                importance: "high",
                confidence: 0.88,
                evidence: "No approver was named.",
              },
            ],
          }
        : null,
    ),
    followUpEmail: {
      ...capability(
        emailState,
        stage === "completed"
          ? {
              subject: "Pilot next steps",
              greeting: "Hello,",
              summary: "The customer confirmed the pilot scope and next steps.",
              decisions: ["Proceed with the pilot. (Owner: Customer team)"],
              actionItems: [
                "Send the implementation plan. (Owner: Alex; Due: 2026-07-30)",
              ],
              openQuestions: ["Who will approve production access?"],
              closing: "Kind regards,",
              tone: "professional",
              confidence: 0.92,
            }
          : null,
      ),
      state: stage === "prerequisites" ? "not_generated" : emailState,
      generationAvailable: stage === "prerequisites" || stage === "completed",
      tone: stage === "email" || stage === "completed" ? "professional" : null,
    },
  };
}

function generationWorkspace(
  stage:
    "not_started" | "extractions" | "prerequisites" | "email" | "completed",
) {
  return {
    ...workspace(stage),
    createdCapabilities:
      stage === "extractions"
        ? [
            "executive_summary",
            "decisions",
            "action_items",
            "risks_blockers",
            "open_questions",
          ]
        : stage === "email"
          ? ["follow_up_email"]
          : [],
    reusedCapabilities: [],
  };
}
