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

test("meeting detail generates and persists all six Meeting Intelligence capabilities", async ({
  page,
}) => {
  let executiveSummaryRequested = false;
  let decisionsRequested = false;
  let decisionsStatusReads = 0;
  let actionItemsRequested = false;
  let actionItemsStatusReads = 0;
  let risksBlockersRequested = false;
  let risksBlockersStatusReads = 0;
  let openQuestionsRequested = false;
  let openQuestionsStatusReads = 0;
  let followUpEmailRequested = false;
  let followUpEmailStatusReads = 0;
  await page.route(
    "http://localhost:8000/api/v1/meetings/meeting-1**",
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/intelligence/executive-summary")) {
        if (route.request().method() === "POST") {
          executiveSummaryRequested = true;
          await route.fulfill({
            status: 202,
            json: {
              jobId: "job-1",
              status: "queued",
              created: true,
              transcriptVersion: 1,
              requestedAt: "2026-07-18T00:00:00Z",
              startedAt: null,
              completedAt: null,
            },
          });
          return;
        }
        await route.fulfill({
          json: !executiveSummaryRequested
            ? {
                state: "empty",
                generationAvailable: true,
                unavailableReason: null,
                jobId: null,
                transcriptVersion: null,
                requestedAt: null,
                startedAt: null,
                generatedAt: null,
                safeMessage: null,
                executiveSummary: null,
              }
            : {
                state: "completed",
                generationAvailable: false,
                unavailableReason: null,
                jobId: "job-1",
                transcriptVersion: 1,
                requestedAt: "2026-07-18T00:00:00Z",
                startedAt: "2026-07-18T00:00:01Z",
                generatedAt: "2026-07-18T00:00:02Z",
                safeMessage: null,
                executiveSummary: {
                  executiveSummary:
                    "The customer discussed expansion plans and confirmed budget.",
                  meetingType: "sales_discovery",
                  sentiment: "positive",
                  confidence: 0.82,
                },
              },
        });
        return;
      }
      if (path.endsWith("/intelligence/decisions")) {
        if (route.request().method() === "POST") {
          decisionsRequested = true;
          await route.fulfill({
            status: 202,
            json: {
              jobId: "job-2",
              status: "queued",
              created: true,
              transcriptVersion: 1,
              requestedAt: "2026-07-18T00:00:00Z",
              startedAt: null,
              completedAt: null,
            },
          });
          return;
        }
        if (!decisionsRequested) {
          await route.fulfill({
            json: {
              state: "empty",
              generationAvailable: true,
              unavailableReason: null,
              jobId: null,
              transcriptVersion: null,
              requestedAt: null,
              startedAt: null,
              generatedAt: null,
              safeMessage: null,
              decisions: null,
            },
          });
          return;
        }
        decisionsStatusReads += 1;
        await route.fulfill({
          json:
            decisionsStatusReads === 1
              ? {
                  state: "queued",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-2",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: null,
                  generatedAt: null,
                  safeMessage: null,
                  decisions: null,
                }
              : {
                  state: "completed",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-2",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: "2026-07-18T00:00:01Z",
                  generatedAt: "2026-07-18T00:00:02Z",
                  safeMessage: null,
                  decisions: {
                    decisions: [
                      {
                        decision: "Proceed with the September pilot.",
                        owner: "Jane Smith",
                        status: "confirmed",
                        confidence: 0.94,
                        evidence:
                          "The transcript records agreement to begin the pilot in September.",
                      },
                    ],
                  },
                },
        });
        return;
      }
      if (path.endsWith("/intelligence/action-items")) {
        if (route.request().method() === "POST") {
          actionItemsRequested = true;
          await route.fulfill({
            status: 202,
            json: {
              jobId: "job-3",
              status: "queued",
              created: true,
              transcriptVersion: 1,
              requestedAt: "2026-07-18T00:00:00Z",
              startedAt: null,
              completedAt: null,
            },
          });
          return;
        }
        if (!actionItemsRequested) {
          await route.fulfill({
            json: {
              state: "empty",
              generationAvailable: true,
              unavailableReason: null,
              jobId: null,
              transcriptVersion: null,
              requestedAt: null,
              startedAt: null,
              generatedAt: null,
              safeMessage: null,
              actionItems: null,
            },
          });
          return;
        }
        actionItemsStatusReads += 1;
        await route.fulfill({
          json:
            actionItemsStatusReads === 1
              ? {
                  state: "queued",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-3",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: null,
                  generatedAt: null,
                  safeMessage: null,
                  actionItems: null,
                }
              : {
                  state: "completed",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-3",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: "2026-07-18T00:00:01Z",
                  generatedAt: "2026-07-18T00:00:02Z",
                  safeMessage: null,
                  actionItems: {
                    actionItems: [
                      {
                        task: "Send the revised commercial proposal.",
                        owner: "Kevin",
                        dueDate: "2026-08-01",
                        priority: "high",
                        status: "open",
                        confidence: 0.92,
                        evidence:
                          "Kevin committed to send the revised proposal by 2026-08-01.",
                      },
                    ],
                  },
                },
        });
        return;
      }
      if (path.endsWith("/intelligence/risks-blockers")) {
        if (route.request().method() === "POST") {
          risksBlockersRequested = true;
          await route.fulfill({
            status: 202,
            json: {
              jobId: "job-4",
              status: "queued",
              created: true,
              transcriptVersion: 1,
              requestedAt: "2026-07-18T00:00:00Z",
              startedAt: null,
              completedAt: null,
            },
          });
          return;
        }
        if (!risksBlockersRequested) {
          await route.fulfill({
            json: {
              state: "empty",
              generationAvailable: true,
              unavailableReason: null,
              jobId: null,
              transcriptVersion: null,
              requestedAt: null,
              startedAt: null,
              generatedAt: null,
              safeMessage: null,
              risksBlockers: null,
            },
          });
          return;
        }
        risksBlockersStatusReads += 1;
        await route.fulfill({
          json:
            risksBlockersStatusReads === 1
              ? {
                  state: "queued",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-4",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: null,
                  generatedAt: null,
                  safeMessage: null,
                  risksBlockers: null,
                }
              : {
                  state: "completed",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-4",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: "2026-07-18T00:00:01Z",
                  generatedAt: "2026-07-18T00:00:02Z",
                  safeMessage: null,
                  risksBlockers: {
                    risks: [
                      {
                        risk: "Procurement approval may delay implementation.",
                        category: "procurement",
                        severity: "high",
                        owner: "Customer Procurement",
                        confidence: 0.93,
                        evidence:
                          "The customer said procurement usually takes six weeks.",
                      },
                    ],
                  },
                },
        });
        return;
      }
      if (path.endsWith("/intelligence/open-questions")) {
        if (route.request().method() === "POST") {
          openQuestionsRequested = true;
          await route.fulfill({
            status: 202,
            json: {
              jobId: "job-5",
              status: "queued",
              created: true,
              transcriptVersion: 1,
              requestedAt: "2026-07-18T00:00:00Z",
              startedAt: null,
              completedAt: null,
            },
          });
          return;
        }
        if (!openQuestionsRequested) {
          await route.fulfill({
            json: {
              state: "empty",
              generationAvailable: true,
              unavailableReason: null,
              jobId: null,
              transcriptVersion: null,
              requestedAt: null,
              startedAt: null,
              generatedAt: null,
              safeMessage: null,
              openQuestions: null,
            },
          });
          return;
        }
        openQuestionsStatusReads += 1;
        await route.fulfill({
          json:
            openQuestionsStatusReads === 1
              ? {
                  state: "queued",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-5",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: null,
                  generatedAt: null,
                  safeMessage: null,
                  openQuestions: null,
                }
              : {
                  state: "completed",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-5",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: "2026-07-18T00:00:01Z",
                  generatedAt: "2026-07-18T00:00:02Z",
                  safeMessage: null,
                  openQuestions: {
                    openQuestions: [
                      {
                        question:
                          "Has legal approved the final contract terms?",
                        owner: "Customer Legal",
                        importance: "high",
                        confidence: 0.92,
                        evidence:
                          "The customer said legal approval was still outstanding.",
                      },
                    ],
                  },
                },
        });
        return;
      }
      if (path.endsWith("/intelligence/follow-up-email")) {
        if (route.request().method() === "POST") {
          followUpEmailRequested = true;
          expect(route.request().postDataJSON()).toEqual({ tone: "friendly" });
          await route.fulfill({
            status: 202,
            json: {
              jobId: "job-6",
              status: "queued",
              created: true,
              transcriptVersion: 1,
              tone: "friendly",
              requestedAt: "2026-07-18T00:00:00Z",
              startedAt: null,
              completedAt: null,
            },
          });
          return;
        }
        if (!followUpEmailRequested) {
          await route.fulfill({
            json: {
              state: "empty",
              generationAvailable: true,
              unavailableReason: null,
              jobId: null,
              transcriptVersion: null,
              requestedAt: null,
              startedAt: null,
              generatedAt: null,
              safeMessage: null,
              tone: null,
              followUpEmail: null,
            },
          });
          return;
        }
        followUpEmailStatusReads += 1;
        await route.fulfill({
          json:
            followUpEmailStatusReads === 1
              ? {
                  state: "queued",
                  generationAvailable: false,
                  unavailableReason: null,
                  jobId: "job-6",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: null,
                  generatedAt: null,
                  safeMessage: null,
                  tone: "friendly",
                  followUpEmail: null,
                }
              : {
                  state: "completed",
                  generationAvailable: true,
                  unavailableReason: null,
                  jobId: "job-6",
                  transcriptVersion: 1,
                  requestedAt: "2026-07-18T00:00:00Z",
                  startedAt: "2026-07-18T00:00:01Z",
                  generatedAt: "2026-07-18T00:00:02Z",
                  safeMessage: null,
                  tone: "friendly",
                  followUpEmail: {
                    subject: "Following up on our discussion",
                    greeting: "Hi,",
                    summary:
                      "The customer discussed expansion plans and confirmed budget.",
                    decisions: ["Proceed with the September pilot."],
                    actionItems: [
                      "Send the revised commercial proposal. (Owner: Kevin; Due: 2026-08-01)",
                    ],
                    openQuestions: [
                      "Has legal approved the final contract terms?",
                    ],
                    closing: "Thanks,",
                    tone: "friendly",
                    confidence: 0.95,
                  },
                },
        });
        return;
      }
      if (path.endsWith("/participants")) {
        await route.fulfill({ json: [] });
        return;
      }
      if (path.endsWith("/transcript")) {
        await route.fulfill({
          json: {
            id: "transcript-1",
            meetingId: "meeting-1",
            rawText: "Customer supplied transcript.",
            language: "en",
            version: 1,
            source: "manual",
            createdAt: "2026-07-17T00:00:00Z",
            updatedAt: "2026-07-17T00:00:00Z",
          },
        });
        return;
      }
      if (path.endsWith("/history")) {
        await route.fulfill({
          json: [
            {
              id: "audit-1",
              meetingId: "meeting-1",
              actorUserId: "user-1",
              action: "created",
              entityType: "meeting",
              entityId: "meeting-1",
              changedFields: ["title"],
              version: null,
              createdAt: "2026-07-17T00:00:00Z",
            },
          ],
        });
        return;
      }
      await route.fulfill({
        json: {
          id: "meeting-1",
          organisationId: "organisation-1",
          title: "Acme discovery",
          description: "Discuss expansion.",
          meetingDate: "2026-08-01T00:00:00Z",
          meetingType: "remote",
          status: "scheduled",
          companyId: null,
          ownerUserId: "user-1",
          createdBy: "user-1",
          updatedBy: "user-1",
          createdAt: "2026-07-17T00:00:00Z",
          updatedAt: "2026-07-17T00:00:00Z",
        },
      });
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

  await expect(
    page.getByRole("heading", { name: "Acme discovery" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Intelligence" }).click();
  await page
    .getByRole("button", { name: "Generate Executive Summary" })
    .click();
  await expect(
    page.getByText(/customer discussed expansion plans/i),
  ).toBeVisible();
  await expect(page.getByText("Sales Discovery")).toBeVisible();
  await expect(page.getByText("82%")).toBeVisible();
  await page.getByRole("button", { name: "Generate Decisions" }).click();
  await expect(page.getByText("Decisions generation is queued…")).toBeVisible();
  await expect(
    page.getByText("Proceed with the September pilot."),
  ).toBeVisible();
  await expect(page.getByText("Jane Smith")).toBeVisible();
  await expect(page.getByText("Confirmed", { exact: true })).toBeVisible();
  await expect(page.getByText("94%")).toBeVisible();
  await page.getByRole("button", { name: "Generate Action Items" }).click();
  await expect(
    page.getByText("Action Items generation is queued…"),
  ).toBeVisible();
  await expect(
    page.getByText("Send the revised commercial proposal."),
  ).toBeVisible();
  await expect(page.getByText("Kevin", { exact: true })).toBeVisible();
  await expect(page.getByText("High", { exact: true })).toBeVisible();
  await expect(page.getByText("Open", { exact: true })).toBeVisible();
  await expect(page.getByText("92%")).toBeVisible();
  await page.getByRole("button", { name: "Generate Risks & Blockers" }).click();
  await expect(
    page.getByText("Risks & Blockers generation is queued…"),
  ).toBeVisible();
  await expect(
    page.getByText("Procurement approval may delay implementation."),
  ).toBeVisible();
  await expect(page.getByText("Customer Procurement")).toBeVisible();
  await expect(page.getByText("Procurement", { exact: true })).toBeVisible();
  await expect(page.getByText("93%", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Generate Open Questions" }).click();
  await expect(
    page.getByText("Open Questions generation is queued…"),
  ).toBeVisible();
  await expect(
    page.getByText("Has legal approved the final contract terms?"),
  ).toBeVisible();
  await expect(page.getByText("Customer Legal")).toBeVisible();
  await expect(page.getByText("92%", { exact: true }).last()).toBeVisible();
  await page.getByLabel("Tone").selectOption("friendly");
  await page.getByRole("button", { name: "Draft Follow-up Email" }).click();
  await expect(
    page.getByText("Follow-up Email composition is queued…"),
  ).toBeVisible();
  await expect(
    page.getByText("Subject: Following up on our discussion"),
  ).toBeVisible();
  await expect(page.getByText("Friendly tone · 95% confidence")).toBeVisible();
  await expect(page.getByText("Hi,", { exact: true })).toBeVisible();
  await expect(page.getByText("Thanks,", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Regenerate" })).toBeVisible();

  await page.reload();
  await page.getByRole("tab", { name: "Intelligence" }).click();
  await expect(
    page
      .getByRole("article", { name: "Executive Summary" })
      .getByText(/customer discussed expansion plans/i),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Decisions" })
      .getByText("Proceed with the September pilot."),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Action Items" })
      .getByText("Send the revised commercial proposal."),
  ).toBeVisible();
  await expect(
    page.getByText("Procurement approval may delay implementation."),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Open Questions" })
      .getByText("Has legal approved the final contract terms?"),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Draft Follow-up Email" })
      .getByText("Subject: Following up on our discussion"),
  ).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Executive Summary" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Risks & Blockers" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Open Questions" })
      .getByRole("heading", { name: "Open Questions" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Draft Follow-up Email" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Transcript" }).click();
  await expect(page.getByLabel("Transcript text")).toHaveValue(
    "Customer supplied transcript.",
  );
  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByText("Meeting created")).toBeVisible();
});
