import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
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
            visualEvidence: false,
            presentationMode: false,
            recordingCapture: false,
            transcription: false,
            autoGenerateIntelligenceAfterTranscription: false,
            dataExport: true,
            organisationDeletion: false,
          },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
});

test("landing page explains the current product honestly", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "The AI sales teammate that remembers every customer interaction and turns conversations into action.",
    }),
  ).toBeVisible();
  await expect(
    page.getByText(/recording is consent-gated and never starts implicitly/i),
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

test("private beta onboarding, consent, feedback and admin controls stay product-safe", async ({
  page,
}) => {
  let onboardingStep = 0;
  let acknowledged = false;
  let adminAllowed = true;
  let feedbackPayload: Record<string, unknown> | null = null;

  await page.route("http://localhost:8000/api/v1/beta/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/capabilities")) {
      await route.fallback();
      return;
    }
    if (path.endsWith("/data-notice/acknowledgements")) {
      acknowledged = true;
      await route.fulfill({ json: dataNotice(true) });
      return;
    }
    if (path.endsWith("/data-notice")) {
      await route.fulfill({ json: dataNotice(acknowledged) });
      return;
    }
    if (path.endsWith("/onboarding") && request.method() === "PATCH") {
      const body = request.postDataJSON() as {
        action: string;
        currentStep?: number;
      };
      onboardingStep =
        body.action === "skip" || body.action === "complete"
          ? 9
          : (body.currentStep ?? onboardingStep + 1);
      await route.fulfill({
        json: {
          currentStep: onboardingStep,
          skipped: body.action === "skip",
          completed: onboardingStep === 9,
          completedAt: onboardingStep === 9 ? "2026-07-25T00:00:00Z" : null,
        },
      });
      return;
    }
    if (path.endsWith("/onboarding")) {
      await route.fulfill({
        json: {
          currentStep: onboardingStep,
          skipped: false,
          completed: false,
          completedAt: null,
        },
      });
      return;
    }
    if (path.endsWith("/feedback")) {
      feedbackPayload = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 201,
        json: {
          id: "feedback-1",
          ...feedbackPayload,
          meetingId: null,
          opportunityId: null,
          createdAt: "2026-07-25T00:00:00Z",
        },
      });
      return;
    }
    if (path.endsWith("/admin")) {
      await route.fulfill(
        adminAllowed
          ? { json: betaAdminOverview() }
          : {
              status: 403,
              json: {
                code: "forbidden",
                message: "Administrator access is required.",
                requestId: "beta-member-check",
              },
            },
      );
      return;
    }
    await route.fulfill({ status: 404, json: { message: "Not found" } });
  });

  await page.goto("/onboarding");
  await expect(
    page.getByRole("heading", { name: "Set up your safe first journey" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Start safely" }).click();
  await expect(
    page.getByRole("heading", { name: /Private beta data notice/ }),
  ).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Acknowledge and continue" }).click();
  expect(acknowledged).toBe(true);
  await page.getByRole("button", { name: "Skip onboarding" }).click();
  await expect(
    page.getByRole("heading", { name: "Your workspace is ready" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Feedback" }).click();
  await page.getByLabel("Category").selectOption("confusing");
  await page.getByLabel("Rating").selectOption("4");
  await page
    .getByLabel("Short message")
    .fill("The synthetic beta workflow needs a clearer next step.");
  await page.getByRole("button", { name: "Send feedback" }).click();
  await expect(page.getByText(/your feedback was sent/i)).toBeVisible();
  expect(feedbackPayload).toEqual({
    category: "confusing",
    rating: 4,
    message: "The synthetic beta workflow needs a clearer next step.",
    currentRoute: "/feedback",
  });

  await page.getByRole("link", { name: "Settings" }).click();
  await expect(
    page.getByRole("heading", { name: "Organisation controls" }),
  ).toBeVisible();
  await expect(page.getByLabel(/retention policy/i)).toHaveValue("days_90");
  await expect(page.getByText("0 / 100")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Queue organisation deletion" }),
  ).toHaveCount(0);
  for (const prohibited of ["prompt", "worker", "api key", "provider"]) {
    await expect(page.getByText(new RegExp(prohibited, "i"))).toHaveCount(0);
  }
  if (process.env.CAPTURE_WO_009_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-009-private-beta-admin.png",
      fullPage: true,
    });
  }
  adminAllowed = false;
  await page.reload();
  await expect(
    page.getByRole("alert").filter({
      hasText: "Administrator access is required.",
    }),
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

test("interaction timeline supports deliberate creation and completion without internal controls", async ({
  page,
}) => {
  let created = false;
  let completed = false;
  let createPayload: Record<string, unknown> | null = null;
  const linkedInteraction = interactionRecord({
    id: "interaction-1",
    meetingId: "meeting-1",
    title: "Acme discovery",
    interactionType: "online_meeting",
  });
  const createdInteraction = interactionRecord({
    id: "interaction-2",
    meetingId: null,
    title: "Customer planning workshop",
    interactionType: "workshop",
  });

  await page.route(
    "http://localhost:8000/api/v1/interactions**",
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.endsWith("/companion/brief")) {
        await route.fulfill({ json: emptyBriefResponse() });
        return;
      }
      if (request.method() === "POST" && path.endsWith("/complete")) {
        completed = true;
        await route.fulfill({
          json: {
            ...createdInteraction,
            lifecycleStatus: "completed",
            actualEndAt: "2026-08-04T02:00:00Z",
          },
        });
        return;
      }
      if (request.method() === "POST") {
        createPayload = request.postDataJSON() as Record<string, unknown>;
        created = true;
        await route.fulfill({ status: 201, json: createdInteraction });
        return;
      }
      if (path.endsWith("/interaction-2")) {
        await route.fulfill({
          json: completed
            ? {
                ...createdInteraction,
                lifecycleStatus: "completed",
                actualEndAt: "2026-08-04T02:00:00Z",
              }
            : createdInteraction,
        });
        return;
      }
      await route.fulfill({
        json: {
          items: [
            linkedInteraction,
            ...(created
              ? [
                  completed
                    ? {
                        ...createdInteraction,
                        lifecycleStatus: "completed",
                        actualEndAt: "2026-08-04T02:00:00Z",
                      }
                    : createdInteraction,
                ]
              : []),
          ],
          page: 1,
          pageSize: 100,
          total: created ? 2 : 1,
          pages: 1,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/companies**",
    async (route) => {
      if (new URL(route.request().url()).pathname.endsWith("/company-1")) {
        await route.fulfill({
          json: {
            id: "company-1",
            organisationId: "organisation-1",
            name: "Acme Australia",
            website: null,
            industry: "Technology",
            employeeCount: 120,
            status: "active",
            ownerUserId: "user-1",
            createdAt: "2026-07-01T00:00:00Z",
            updatedAt: "2026-07-01T00:00:00Z",
          },
        });
        return;
      }
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
  await page.route(
    "http://localhost:8000/api/v1/accounts/company-1/brain**",
    async (route) => {
      if (new URL(route.request().url()).pathname.endsWith("/reasoning")) {
        await route.fulfill({
          json: {
            state: "insufficient_history",
            message:
              "Revenue Brain needs at least two completed meeting snapshots before it can identify changes.",
            latest: null,
            history: [],
          },
        });
        return;
      }
      await route.fulfill({ json: [] });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/opportunities**",
    async (route) => {
      await route.fulfill({
        json: {
          items: [{ id: "opportunity-1", name: "Expansion" }],
          page: 1,
          pageSize: 100,
          total: 1,
          pages: 1,
        },
      });
    },
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/interactions");
  await expect(
    page.getByRole("heading", { name: "Interactions" }),
  ).toBeVisible();
  await expect(page.getByText("Acme Australia")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open Meeting Intelligence" }),
  ).toHaveAttribute("href", "/meetings/meeting-1");

  await page.getByRole("link", { name: "Create interaction" }).first().click();
  await page.getByLabel("Title").fill("Customer planning workshop");
  await page.getByLabel("Interaction type").selectOption("workshop");
  await page.getByLabel("Company").selectOption("company-1");
  await page.getByLabel("Opportunity").selectOption("opportunity-1");
  await page.getByRole("button", { name: "Create interaction" }).click();
  await expect(page).toHaveURL(/\/interactions\/interaction-2$/);
  expect(created).toBe(true);
  expect(createPayload).toMatchObject({
    title: "Customer planning workshop",
    interactionType: "workshop",
    companyId: "company-1",
    opportunityId: "opportunity-1",
  });
  await page.getByRole("button", { name: "Complete interaction" }).click();
  await expect(
    page.getByRole("status", { name: "Interaction lifecycle status" }),
  ).toHaveText("Completed");
  expect(completed).toBe(true);
  if (process.env.CAPTURE_WO_011_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-011-interaction-detail.png",
      fullPage: true,
    });
  }

  await page.getByRole("link", { name: "Back to interactions" }).click();
  await expect(
    page.getByRole("heading", { name: "Customer planning workshop" }),
  ).toBeVisible();

  await page.goto("/companies/company-1");
  await expect(
    page.getByRole("heading", { name: "Revenue Brain" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No snapshots yet" }),
  ).toBeVisible();

  await expect(page.getByLabel(/transcript/i)).toHaveCount(0);
  for (const prohibited of [
    "prompt",
    "worker",
    "provider",
    "internal metadata",
  ]) {
    await expect(page.getByText(new RegExp(prohibited, "i"))).toHaveCount(0);
  }
});

test("AI Companion briefs support face-to-face, phone and presentation preparation", async ({
  page,
}) => {
  let faceReviewed = false;
  const interactions = [
    interactionRecord({
      id: "interaction-face",
      title: "On-site pilot planning",
      interactionType: "face_to_face_meeting",
      briefState: "completed",
      briefGeneratedAt: "2026-08-14T02:00:00Z",
    }),
    interactionRecord({
      id: "interaction-phone",
      title: "Pilot next-step call",
      interactionType: "phone_call",
      briefState: "completed",
      briefGeneratedAt: "2026-08-14T02:00:00Z",
    }),
    interactionRecord({
      id: "interaction-presentation",
      title: "Pilot presentation",
      interactionType: "presentation",
      briefState: "completed",
      briefGeneratedAt: "2026-08-14T02:00:00Z",
    }),
  ];

  await page.route(
    "http://localhost:8000/api/v1/interactions**",
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      const match = path.match(/\/interactions\/(interaction-[^/]+)/);
      const interaction = interactions.find((item) => item.id === match?.[1]);
      if (path.endsWith("/companion/brief/review")) {
        faceReviewed = true;
        await route.fulfill({
          json: companionBrief("face_to_face_meeting", true),
        });
        return;
      }
      if (path.endsWith("/companion/brief") && interaction) {
        await route.fulfill({
          json: companionBrief(
            String(interaction.interactionType),
            interaction.id === "interaction-face" && faceReviewed,
          ),
        });
        return;
      }
      if (interaction) {
        await route.fulfill({ json: interaction });
        return;
      }
      await route.fulfill({
        json: {
          items: interactions,
          page: 1,
          pageSize: 100,
          total: interactions.length,
          pages: 1,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/companies**",
    async (route) => {
      await route.fulfill({
        json: {
          items: [{ id: "company-1", name: "Southern Cross Operations" }],
          page: 1,
          pageSize: 100,
          total: 1,
          pages: 1,
        },
      });
    },
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/interactions");
  await expect(page.getByText("Brief ready").first()).toBeVisible();
  await page.getByRole("link", { name: "Open brief" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Prepare for this interaction" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Objectives" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Questions to ask" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Stakeholder focus" }),
  ).toBeVisible();
  await expect(page.getByText("Risks to watch")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Success criteria", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mark as reviewed" }).click();
  await expect(page.getByRole("button", { name: "Reviewed" })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole("button", { name: "Reviewed" })).toBeDisabled();

  await page.goto("/interactions/interaction-phone");
  await expect(page.getByText(/Keep the call concise/i)).toBeVisible();
  await expect(page.getByText("Alex Morgan · champion")).toBeVisible();
  await expect(page.getByText("Provide the security summary.")).toBeVisible();

  await page.goto("/interactions/interaction-presentation");
  await expect(
    page.getByRole("heading", { name: "Presentation guidance" }),
  ).toBeVisible();
  await expect(page.getByText(/seller-prepared material/i)).toBeVisible();
  for (const prohibited of ["prompt", "provider", "worker", "transcript"]) {
    await expect(page.getByText(new RegExp(prohibited, "i"))).toHaveCount(0);
  }
  await expect(page.getByRole("button", { name: /record/i })).toHaveCount(0);
});

test("a presentation supports browser image upload, explicit review and intelligence update", async ({
  page,
}) => {
  let interaction: Record<string, unknown> = interactionRecord({
    id: "interaction-visual",
    title: "Customer solution presentation",
    interactionType: "presentation",
    companyId: "company-visual",
    opportunityId: "opportunity-visual",
  });
  let brief: Record<string, unknown> = emptyBriefResponse();
  let debrief = debriefSession("collecting", {
    interactionId: "interaction-visual",
  });
  let visuals: Record<string, unknown>[] = [];
  let reviewPayload: Record<string, unknown> | null = null;
  let debriefReviewPayload: Record<string, unknown> | null = null;
  let currentUpload: Record<string, unknown> | null = null;
  let workspaceReads = 0;
  let brainVisualReads = 0;

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
            presentationMode: true,
            recordingCapture: false,
            transcription: false,
            autoGenerateIntelligenceAfterTranscription: false,
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
    "http://localhost:8000/api/v1/interactions/interaction-visual**",
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.endsWith("/companion/brief/review")) {
        brief = companionBrief("presentation", true);
        await route.fulfill({ json: brief });
        return;
      }
      if (path.endsWith("/companion/brief")) {
        if (request.method() === "POST") {
          brief = companionBrief("presentation", false);
        }
        await route.fulfill({ json: brief });
        return;
      }
      if (path === "/api/v1/interactions/interaction-visual/complete") {
        interaction = {
          ...interaction,
          lifecycleStatus: "completed",
          actualEndAt: "2026-08-14T02:00:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      if (path.endsWith("/visual-evidence/uploads")) {
        const body = request.postDataJSON() as Record<string, unknown>;
        const seller = body.sourceOwnership === "salesperson_created";
        const id = seller ? "visual-seller" : "visual-1";
        currentUpload = visualEvidence("uploading", {
          id,
          captureSessionId: id,
          visualType: body.visualType,
          sourceOwnership: body.sourceOwnership,
          contextLabel: body.contextLabel,
          filename: body.filename,
          candidates: [],
        });
        await route.fulfill({
          status: 201,
          json: {
            ...currentUpload,
            uploadUrl: `/api/v1/interactions/interaction-visual/visual-evidence/${id}/content?token=test-signed-token`,
            uploadExpiresAt: "2026-08-14T02:05:00Z",
          },
        });
        return;
      }
      if (path.endsWith("/content") && request.method() === "PUT") {
        await route.fulfill({ status: 204, body: "" });
        return;
      }
      if (path.endsWith("/complete")) {
        currentUpload = {
          ...(currentUpload ?? {}),
          processingStatus: "uploaded",
        };
        await route.fulfill({
          json: currentUpload,
        });
        return;
      }
      if (path.endsWith("/process")) {
        if (currentUpload?.sourceOwnership === "salesperson_created") {
          currentUpload = {
            ...currentUpload,
            processingStatus: "completed",
            processingAttempts: 1,
            candidates: [],
          };
          visuals = [...visuals, currentUpload];
        } else {
          currentUpload = {
            ...currentUpload,
            processingStatus: "review",
            processingAttempts: 1,
            candidates: [
              visualCandidate(),
              visualCandidate({
                id: "candidate-visual-unsupported",
                category: "commercial_intent",
                statement:
                  "Our slide proves the customer will buy this quarter.",
                originalStatement:
                  "Our slide proves the customer will buy this quarter.",
              }),
            ],
          };
          visuals = [currentUpload];
        }
        await route.fulfill({ json: currentUpload });
        return;
      }
      if (path.includes("/visual-evidence/") && path.endsWith("/review")) {
        reviewPayload = request.postDataJSON() as Record<string, unknown>;
        visuals = [
          {
            ...visualEvidence("completed"),
            candidates: [
              visualCandidate({
                statement: "Customer requested a reviewed security workshop.",
                validationState: "verified",
                reviewState: "accepted",
                acceptedEvidenceId: "evidence-visual-accepted",
                edited: true,
              }),
              visualCandidate({
                id: "candidate-visual-unsupported",
                category: "commercial_intent",
                statement:
                  "Our slide proves the customer will buy this quarter.",
                originalStatement:
                  "Our slide proves the customer will buy this quarter.",
                validationState: "rejected",
                reviewState: "rejected",
              }),
            ],
            interactionIntelligenceId: "intelligence-visual-1",
            revenueBrainSnapshotId: "brain-visual-1",
            acceptedCount: 1,
            rejectedCount: 1,
            interactionUpdated: true,
            revenueBrainUpdated: true,
          },
        ];
        await route.fulfill({ json: visuals[0] });
        return;
      }
      if (path.endsWith("/visual-evidence")) {
        await route.fulfill({ json: visuals });
        return;
      }
      if (path.endsWith("/debrief") && request.method() === "POST") {
        await route.fulfill({ status: 201, json: debrief });
        return;
      }
      if (path.endsWith("/response")) {
        debrief = debriefSession("collecting", {
          interactionId: "interaction-visual",
          questionCount: 1,
          currentQuestion: {
            status: "complete",
            question: null,
            reason: "Presentation-specific evidence is sufficient for review.",
            target: null,
            priority: null,
          },
          canFinish: true,
          turns: [
            {
              id: "turn-presentation-1",
              turnNumber: 1,
              question: debrief.currentQuestion,
              answerText:
                "The customer asked about security and requested a workshop before the next meeting.",
              inputMode: "text",
              createdAt: "2026-08-14T02:12:00Z",
            },
          ],
        });
        await route.fulfill({ json: debrief });
        return;
      }
      if (path.endsWith("/finish")) {
        debrief = debriefSession("review", {
          interactionId: "interaction-visual",
          currentQuestion: null,
          candidates: [
            {
              ...reportedCandidate(),
              evidenceCategory: "action_item",
              statement: "The customer requested a security workshop.",
              originalStatement: "The customer requested a security workshop.",
            },
          ],
        });
        await route.fulfill({ json: debrief });
        return;
      }
      if (path.includes("/debrief/") && path.endsWith("/review")) {
        debriefReviewPayload = request.postDataJSON() as Record<
          string,
          unknown
        >;
        debrief = debriefSession("completed", {
          interactionId: "interaction-visual",
          currentQuestion: null,
          candidates: [
            {
              ...reportedCandidate(),
              evidenceCategory: "action_item",
              statement: "The customer requested a security workshop.",
              originalStatement: "The customer requested a security workshop.",
              validationState: "verified",
              userReviewState: "accepted",
              acceptedEvidenceId: "evidence-debrief-accepted",
            },
          ],
          interactionIntelligenceId: "intelligence-debrief-1",
          revenueBrainSnapshotId: "brain-debrief-1",
          completedAt: "2026-08-14T02:15:00Z",
          acceptedCount: 1,
          rejectedCount: 0,
          interactionUpdated: true,
          revenueBrainUpdated: true,
        });
        await route.fulfill({ json: debrief });
        return;
      }
      if (path.includes("/debrief/session-1")) {
        await route.fulfill({ json: debrief });
        return;
      }
      await route.fulfill({ json: interaction });
    },
  );

  await page.route(
    "http://localhost:8000/api/v1/opportunities/opportunity-visual/workspace",
    async (route) => {
      workspaceReads += 1;
      await route.fulfill({
        json: {
          ...opportunityWorkspace(false, false),
          opportunity: {
            ...opportunity(),
            id: "opportunity-visual",
            companyId: "company-visual",
            name: "Customer security programme",
            companyName: "Southern Cross Operations",
            ownerName: "Alex Morgan",
          },
          reportedIntelligence:
            debrief.lifecycleStatus === "completed"
              ? {
                  id: "intelligence-debrief-1",
                  interactionId: "interaction-visual",
                  generatedAt: "2026-08-14T02:15:00Z",
                  sourceLabel: "Reported by you",
                  items: [
                    {
                      evidenceId: "evidence-debrief-accepted",
                      category: "action_item",
                      statement: "The customer requested a security workshop.",
                      origin: "salesperson_reported",
                      sourceLabel: "Reported by you",
                      validationState: "verified",
                    },
                  ],
                }
              : null,
          visualIntelligence: visualIntelligencePayload(),
          latestInteractionCapture: null,
        },
      });
    },
  );
  await page.route("http://localhost:8000/api/v1/meetings**", async (route) => {
    await route.fulfill({
      json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
    });
  });
  await page.route(
    "http://localhost:8000/api/v1/companies/company-visual",
    async (route) => {
      await route.fulfill({
        json: {
          id: "company-visual",
          organisationId: "organisation-1",
          name: "Southern Cross Operations",
          website: null,
          industry: "Professional services",
          employeeCount: 75,
          status: "active",
          ownerUserId: "user-1",
          createdAt: "2026-08-01T00:00:00Z",
          updatedAt: "2026-08-14T02:15:00Z",
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/accounts/company-visual/brain**",
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/reasoning")) {
        await route.fulfill({
          json: {
            state: "insufficient_history",
            message:
              "Revenue Brain needs more history before it can identify longitudinal changes.",
            latest: null,
            history: [],
          },
        });
        return;
      }
      if (path.endsWith("/visual-evidence")) {
        brainVisualReads += 1;
        await route.fulfill({
          json: [
            {
              id: "brain-visual-1",
              interactionId: "interaction-visual",
              opportunityId: "opportunity-visual",
              interactionTitle: "Customer solution presentation",
              interactionType: "presentation",
              interactionDate: "2026-08-14T02:00:00Z",
              createdAt: "2026-08-14T02:10:00Z",
              sourceLabel: "customer whiteboard",
              visualType: "whiteboard",
              items: visualIntelligencePayload().items,
            },
          ],
        });
        return;
      }
      await route.fulfill({ json: [] });
    },
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/sign-in");
  await page
    .getByRole("link", { name: "Continue with development identity" })
    .click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/interactions/interaction-visual");
  await page.getByRole("button", { name: "Prepare brief" }).click();
  await expect(
    page.getByRole("heading", { name: "Presentation guidance" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mark as reviewed" }).click();
  await expect(page.getByRole("button", { name: "Reviewed" })).toBeDisabled();
  await page.getByRole("button", { name: "Complete interaction" }).click();
  await expect(
    page.getByRole("status", { name: "Interaction lifecycle status" }),
  ).toHaveText("Completed");
  await expect(
    page.getByRole("heading", { name: "Visual evidence" }),
  ).toBeVisible();
  await expect(
    page.getByText(/never treated as customer-confirmed buying signals/i),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add whiteboard or photo" }).click();
  await page.getByLabel("Choose an image").setInputFiles({
    name: "customer-question.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64",
    ),
  });
  await expect(page.getByAltText("Selected visual preview")).toBeVisible();
  await page
    .getByLabel("Context label (optional)")
    .fill("Customer requested a security workshop");
  await page.getByLabel(/I am authorised to upload this image/i).check();
  await page.getByRole("button", { name: "Upload and prepare review" }).click();
  await expect(
    page.getByRole("heading", { name: "Review suggested evidence" }),
  ).toBeVisible();
  await page
    .getByLabel("Suggested statement")
    .first()
    .fill("Customer requested a reviewed security workshop.");
  await page.getByRole("radio", { name: "Reject" }).nth(1).check();
  await page.getByRole("button", { name: "Finish review" }).click();
  await expect(
    page.getByText(/added to Interaction Intelligence and Revenue Brain/i),
  ).toBeVisible();
  expect(reviewPayload).toMatchObject({
    decisions: [
      {
        candidateId: "candidate-visual-1",
        decision: "accept",
        statement: "Customer requested a reviewed security workshop.",
      },
      {
        candidateId: "candidate-visual-unsupported",
        decision: "reject",
        statement: null,
      },
    ],
  });
  await expect(
    page.getByText("Accepted · AI-interpreted, user-reviewed"),
  ).toBeVisible();
  await expect(page.getByText("Rejected · not used downstream")).toBeVisible();

  await page.getByRole("button", { name: "Add presentation context" }).click();
  await page.getByLabel("Choose an image").setInputFiles({
    name: "seller-slide.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64",
    ),
  });
  await page
    .getByLabel("Context label (optional)")
    .fill("Our slide says the customer will buy this quarter");
  await page.getByLabel(/I am authorised to upload this image/i).check();
  await page.getByRole("button", { name: "Upload and prepare review" }).click();
  await expect(page.getByText(/saved as presentation context/i)).toBeVisible();
  await expect(
    page.getByText(/Salesperson Created · Seller material · context only/i),
  ).toBeVisible();

  await page.getByRole("checkbox", { name: /safely stopped/i }).check();
  await page.getByRole("button", { name: "Start typed debrief" }).click();
  await page
    .getByLabel("Your answer")
    .fill(
      "The customer asked about security and requested a workshop before the next meeting.",
    );
  await page.getByRole("button", { name: "Save answer" }).click();
  await page.getByRole("button", { name: "Review captured evidence" }).click();
  await expect(page.getByText("Reported by you")).toBeVisible();
  await page
    .getByRole("button", { name: "Finish review and update intelligence" })
    .click();
  await expect(page.getByText("Debrief complete")).toBeVisible();
  expect(debriefReviewPayload).toMatchObject({
    decisions: [{ decision: "accept" }],
  });

  await page.reload();
  await expect(
    page.getByText("Accepted · AI-interpreted, user-reviewed"),
  ).toBeVisible();
  await expect(
    page.getByText(/Our slide says the customer will buy this quarter/i),
  ).toHaveCount(0);
  const hasHorizontalOverflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
  if (process.env.CAPTURE_WO_014_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-014-visual-evidence-review.png",
      fullPage: true,
    });
  }

  await page.goto("/opportunities/opportunity-visual");
  await expect(
    page.getByRole("heading", {
      name: "Latest visual interaction intelligence",
    }),
  ).toBeVisible();
  await expect(page.getByText("customer whiteboard")).toBeVisible();
  await expect(
    page.getByText("Customer requested a reviewed security workshop."),
  ).toBeVisible();
  await expect(page.getByText("Reported by you")).toBeVisible();
  await page.getByRole("button", { name: "Refresh workspace" }).click();
  await expect(
    page.getByText("Customer requested a reviewed security workshop."),
  ).toBeVisible();
  expect(workspaceReads).toBeGreaterThanOrEqual(2);

  await page.goto("/companies/company-visual");
  await expect(
    page.getByRole("heading", { name: "Reviewed visual evidence" }),
  ).toBeVisible();
  await expect(page.getByText("customer whiteboard")).toBeVisible();
  await expect(
    page.getByText("Customer requested a reviewed security workshop."),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("customer whiteboard")).toBeVisible();
  expect(brainVisualReads).toBeGreaterThanOrEqual(2);
  await expect(page.getByRole("button", { name: /record/i })).toHaveCount(0);
});

test("a completed phone call supports a typed debrief, review and source-aware update", async ({
  page,
}) => {
  const interaction = interactionRecord({
    id: "interaction-debrief",
    title: "Pricing follow-up call",
    interactionType: "phone_call",
    lifecycleStatus: "completed",
    actualEndAt: "2026-08-14T02:00:00Z",
  });
  let debrief = debriefSession("collecting");

  await page.route(
    "http://localhost:8000/api/v1/interactions/interaction-debrief**",
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.endsWith("/companion/brief")) {
        await route.fulfill({ json: emptyBriefResponse() });
        return;
      }
      if (path.endsWith("/debrief") && request.method() === "POST") {
        await route.fulfill({ status: 201, json: debrief });
        return;
      }
      if (path.endsWith("/response")) {
        debrief = debriefSession("collecting", {
          questionCount: 1,
          currentQuestion: {
            status: "complete",
            question: null,
            reason: "The reported evidence is sufficient for review.",
            target: null,
            priority: null,
          },
          canFinish: true,
          turns: [
            {
              id: "turn-1",
              turnNumber: 1,
              question: debrief.currentQuestion,
              answerText:
                "Jordan confirmed the budget and I will send the proposal.",
              inputMode: "text",
              createdAt: "2026-08-14T02:02:00Z",
            },
          ],
        });
        await route.fulfill({ json: debrief });
        return;
      }
      if (path.endsWith("/finish")) {
        debrief = debriefSession("review", {
          currentQuestion: null,
          candidates: [reportedCandidate()],
        });
        await route.fulfill({ json: debrief });
        return;
      }
      if (path.endsWith("/review")) {
        debrief = debriefSession("completed", {
          currentQuestion: null,
          candidates: [
            {
              ...reportedCandidate(),
              statement: "Jordan confirmed the budget owner.",
              validationState: "verified",
              userReviewState: "accepted",
              acceptedEvidenceId: "evidence-accepted",
              edited: true,
            },
          ],
          interactionIntelligenceId: "intelligence-1",
          revenueBrainSnapshotId: "brain-1",
          completedAt: "2026-08-14T02:05:00Z",
          acceptedCount: 1,
          rejectedCount: 0,
          interactionUpdated: true,
          revenueBrainUpdated: true,
        });
        await route.fulfill({ json: debrief });
        return;
      }
      if (path.includes("/debrief/session-1")) {
        await route.fulfill({ json: debrief });
        return;
      }
      await route.fulfill({ json: interaction });
    },
  );

  await page.goto("/interactions/interaction-debrief");
  await expect(
    page.getByRole("heading", {
      name: "Capture what changed while it is fresh",
    }),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: /safely stopped/i }).check();
  await page.getByRole("button", { name: "Start typed debrief" }).click();
  await page
    .getByLabel("Your answer")
    .fill("Jordan confirmed the budget and I will send the proposal.");
  await page.getByRole("button", { name: "Save answer" }).click();
  await page.getByRole("button", { name: "Review captured evidence" }).click();
  await expect(page.getByText("Reported by you")).toBeVisible();
  await page
    .getByLabel("Evidence statement")
    .fill("Jordan confirmed the budget owner.");
  await page
    .getByRole("button", { name: "Finish review and update intelligence" })
    .click();
  await expect(page.getByText("Debrief complete")).toBeVisible();
  await expect(page.getByText(/Reported by you/)).toBeVisible();
});

test("mobile Companion recording path persists a consented transcript into existing intelligence surfaces", async ({
  page,
}) => {
  let interaction: Record<string, unknown> = interactionRecord({
    id: "interaction-recording",
    title: "On-site recording foundation",
    interactionType: "face_to_face_meeting",
    meetingId: "meeting-1",
    companyId: "company-1",
    opportunityId: "opportunity-1",
    briefState: "completed",
    briefGeneratedAt: "2026-08-14T02:00:00Z",
  });
  let briefReviewed = false;
  let recordingCreated = false;
  let recordingLifecycle = "created";
  let transcriptionReads = 0;
  let chunkUploadAttempts = 0;
  let intelligenceGenerated = false;
  const markers: Array<Record<string, unknown>> = [];
  const visuals: Array<Record<string, unknown>> = [];
  let recordingDebrief = debriefSession("collecting", {
    interactionId: "interaction-recording",
    currentQuestion: {
      status: "ask",
      question: "What important outcome might the recording have missed?",
      reason: "Fill the remaining capture gaps.",
      target: "other",
      priority: "high",
    },
  });

  const recording = () => ({
    id: "recording-1",
    interactionId: "interaction-recording",
    captureSessionId: "capture-recording-1",
    recordingType: "live_audio_recording",
    lifecycleStatus: recordingLifecycle,
    consentState: "acknowledged",
    startedAt: recordingCreated ? "2026-08-14T02:10:00Z" : null,
    stoppedAt:
      recordingLifecycle === "recording" ? null : "2026-08-14T02:11:00Z",
    durationSeconds: recordingLifecycle === "recording" ? null : 60,
    expectedMimeType: "audio/webm",
    finalMimeType: recordingLifecycle === "recording" ? null : "audio/webm",
    totalBytes: recordingLifecycle === "recording" ? 0 : 36,
    chunkCount: recordingLifecycle === "recording" ? 0 : 1,
    uploadCompletedAt:
      recordingLifecycle === "recording" ? null : "2026-08-14T02:11:00Z",
    transcriptionStatus:
      recordingLifecycle === "completed"
        ? "completed"
        : recordingLifecycle === "uploaded"
          ? "processing"
          : "queued",
    transcriptionAttempts: recordingLifecycle === "completed" ? 1 : 0,
    failureCode: null,
    autoIntelligenceStatus: "disabled",
    sessionExpiresAt: "2026-08-15T02:10:00Z",
    providerMode: "mock",
    externalProcessing: false,
    createdAt: "2026-08-14T02:10:00Z",
    updatedAt: "2026-08-14T02:11:00Z",
  });

  await page.addInitScript(() => {
    class DeterministicMediaRecorder {
      static isTypeSupported(type: string) {
        return type.startsWith("audio/webm");
      }

      state: RecordingState = "inactive";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      onerror: (() => void) | null = null;

      start() {
        this.state = "recording";
      }

      pause() {
        this.state = "paused";
      }

      resume() {
        this.state = "recording";
      }

      stop() {
        this.state = "inactive";
        this.ondataavailable?.({
          data: new Blob(
            [
              new Uint8Array([0x1a, 0x45, 0xdf, 0xa3]),
              "synthetic-browser-audio",
            ],
            { type: "audio/webm" },
          ),
        });
        queueMicrotask(() => this.onstop?.());
      }
    }

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => ({
          getTracks: () => [{ stop: () => undefined }],
        }),
      },
    });
    Object.defineProperty(globalThis, "MediaRecorder", {
      configurable: true,
      value: DeterministicMediaRecorder,
    });
  });

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
            recordingCapture: true,
            transcription: true,
            autoGenerateIntelligenceAfterTranscription: false,
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
    "http://localhost:8000/api/v1/interactions/interaction-recording**",
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.endsWith("/companion/brief/review")) {
        briefReviewed = true;
        await route.fulfill({
          json: companionBrief("face_to_face_meeting", true),
        });
        return;
      }
      if (path.endsWith("/companion/brief")) {
        await route.fulfill({
          json: companionBrief("face_to_face_meeting", briefReviewed),
        });
        return;
      }
      if (path.endsWith("/companion/markers")) {
        if (request.method() === "POST") {
          const body = request.postDataJSON() as {
            markerType: string;
            recordingOffsetMs: number | null;
          };
          const marker = {
            id: `marker-${markers.length + 1}`,
            interactionId: "interaction-recording",
            createdByUserId: "user-1",
            markerType: body.markerType,
            recordingOffsetMs: body.recordingOffsetMs,
            createdAt: "2026-08-14T02:11:00Z",
          };
          markers.push(marker);
          await route.fulfill({ status: 201, json: marker });
        } else {
          await route.fulfill({ json: markers });
        }
        return;
      }
      if (path.endsWith("/visual-evidence/uploads")) {
        await route.fulfill({
          status: 201,
          json: visualEvidence("uploading", {
            interactionId: "interaction-recording",
            uploadUrl: `${path}/visual-1/content?token=recording-test`,
            uploadExpiresAt: "2026-08-14T02:20:00Z",
          }),
        });
        return;
      }
      if (path.endsWith("/visual-evidence/visual-1/complete")) {
        await route.fulfill({
          json: visualEvidence("uploaded", {
            interactionId: "interaction-recording",
          }),
        });
        return;
      }
      if (path.endsWith("/visual-evidence/visual-1/process")) {
        const completedVisual = visualEvidence("completed", {
          interactionId: "interaction-recording",
        });
        visuals.splice(0, visuals.length, completedVisual);
        await route.fulfill({ json: completedVisual });
        return;
      }
      if (path.endsWith("/visual-evidence")) {
        await route.fulfill({ json: visuals });
        return;
      }
      if (
        path === "/api/v1/interactions/interaction-recording/start" &&
        request.method() === "POST"
      ) {
        interaction = {
          ...interaction,
          lifecycleStatus: "in_progress",
          actualStartAt: "2026-08-14T02:10:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      if (
        path === "/api/v1/interactions/interaction-recording/complete" &&
        request.method() === "POST"
      ) {
        interaction = {
          ...interaction,
          lifecycleStatus: "completed",
          actualEndAt: "2026-08-14T02:15:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      if (path.endsWith("/recordings") && request.method() === "GET") {
        await route.fulfill({ json: recordingCreated ? [recording()] : [] });
        return;
      }
      if (path.endsWith("/recordings") && request.method() === "POST") {
        recordingCreated = true;
        await route.fulfill({ status: 201, json: recording() });
        return;
      }
      if (path.endsWith("/start")) {
        recordingLifecycle = "recording";
        await route.fulfill({ json: recording() });
        return;
      }
      if (path.endsWith("/pause") || path.endsWith("/resume")) {
        await route.fulfill({ json: recording() });
        return;
      }
      if (path.endsWith("/chunks") && request.method() === "POST") {
        const body = request.postDataJSON() as {
          byteSize: number;
          checksumSha256: string;
          sequenceNumber: number;
        };
        await route.fulfill({
          status: 201,
          json: {
            id: "chunk-1",
            recordingSessionId: "recording-1",
            sequenceNumber: body.sequenceNumber,
            byteSize: body.byteSize,
            checksumSha256: body.checksumSha256,
            uploadState: "pending",
            uploadedAt: null,
            createdAt: "2026-08-14T02:10:00Z",
            uploadUrl: `${path}/chunk-1/content?token=short-lived-test-token`,
            uploadExpiresAt: "2026-08-14T02:15:00Z",
          },
        });
        return;
      }
      if (path.endsWith("/content") && request.method() === "PUT") {
        if (path.includes("/chunks/")) {
          chunkUploadAttempts += 1;
          await route.fulfill({
            status: chunkUploadAttempts === 1 ? 503 : 204,
          });
        } else {
          await route.fulfill({ status: 204 });
        }
        return;
      }
      if (path.endsWith("/complete") && path.includes("/chunks/")) {
        await route.fulfill({ json: { uploadState: "verified" } });
        return;
      }
      if (path.endsWith("/stop")) {
        recordingLifecycle = "uploading";
        await route.fulfill({ json: recording() });
        return;
      }
      if (path.endsWith("/finalize")) {
        recordingLifecycle = "uploaded";
        await route.fulfill({ json: recording() });
        return;
      }
      if (path.endsWith("/transcription")) {
        transcriptionReads += 1;
        const completed = transcriptionReads > 1;
        if (completed) recordingLifecycle = "completed";
        await route.fulfill({
          json: {
            recordingId: "recording-1",
            status: completed ? "completed" : "processing",
            transcriptVersionId: completed
              ? "transcript-version-recorded"
              : null,
            transcriptId: completed ? "transcript-1" : null,
            meetingId: completed ? "meeting-1" : null,
            version: completed ? 1 : null,
            source: completed ? "recorded_audio" : null,
            language: completed ? "en-AU" : null,
            text: completed
              ? "The customer approved the pilot and confirmed procurement ownership."
              : null,
            segments: completed
              ? [
                  {
                    sequenceNumber: 0,
                    startMs: 0,
                    endMs: 60_000,
                    speakerLabel: null,
                    text: "The customer approved the pilot and confirmed procurement ownership.",
                    sourceConfidence: null,
                  },
                ]
              : [],
            completedAt: completed ? "2026-08-14T02:12:00Z" : null,
            safeMessage: completed
              ? "Transcription is ready."
              : "Transcription is processing.",
          },
        });
        return;
      }
      if (path.endsWith("/debrief") && request.method() === "POST") {
        await route.fulfill({ status: 201, json: recordingDebrief });
        return;
      }
      if (path.endsWith("/response")) {
        recordingDebrief = debriefSession("collecting", {
          interactionId: "interaction-recording",
          questionCount: 1,
          currentQuestion: {
            status: "complete",
            question: null,
            reason: "The remaining gap is captured.",
            target: null,
            priority: null,
          },
          canFinish: true,
          turns: [
            {
              id: "recording-turn-1",
              turnNumber: 1,
              question: recordingDebrief.currentQuestion,
              answerText: "Morgan owns the final security review.",
              inputMode: "text",
              createdAt: "2026-08-14T02:16:00Z",
            },
          ],
        });
        await route.fulfill({ json: recordingDebrief });
        return;
      }
      if (path.endsWith("/finish")) {
        recordingDebrief = debriefSession("review", {
          interactionId: "interaction-recording",
          currentQuestion: null,
          candidates: [reportedCandidate()],
        });
        await route.fulfill({ json: recordingDebrief });
        return;
      }
      if (path.endsWith("/review")) {
        recordingDebrief = debriefSession("completed", {
          interactionId: "interaction-recording",
          currentQuestion: null,
          candidates: [
            {
              ...reportedCandidate(),
              validationState: "verified",
              userReviewState: "accepted",
              acceptedEvidenceId: "recording-gap-evidence",
            },
          ],
          interactionIntelligenceId: "recording-gap-intelligence",
          revenueBrainSnapshotId: "recording-gap-brain",
          completedAt: "2026-08-14T02:18:00Z",
          acceptedCount: 1,
          rejectedCount: 0,
          interactionUpdated: true,
          revenueBrainUpdated: true,
        });
        await route.fulfill({ json: recordingDebrief });
        return;
      }
      if (path.includes("/debrief/session-1")) {
        await route.fulfill({ json: recordingDebrief });
        return;
      }
      await route.fulfill({ json: interaction });
    },
  );

  await page.route("http://localhost:8000/api/v1/meetings**", async (route) => {
    await route.fulfill({
      json: {
        items: [opportunityMeeting()],
        page: 1,
        pageSize: 100,
        total: 1,
        pages: 1,
      },
    });
  });
  await page.route(
    "http://localhost:8000/api/v1/meetings/meeting-1**",
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/participants") || path.endsWith("/history")) {
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
              "The customer approved the pilot and confirmed procurement ownership.",
            language: "en-AU",
            version: 1,
            source: "recorded_audio",
            createdAt: "2026-08-14T02:12:00Z",
            updatedAt: "2026-08-14T02:12:00Z",
          },
        });
        return;
      }
      if (path.endsWith("/intelligence/generate")) {
        intelligenceGenerated = true;
        await route.fulfill({
          status: 202,
          json: generationWorkspace("completed"),
        });
        return;
      }
      if (path.endsWith("/intelligence")) {
        await route.fulfill({
          json: workspace(intelligenceGenerated ? "completed" : "not_started"),
        });
        return;
      }
      await route.fulfill({ json: meeting() });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/opportunities/opportunity-1**",
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      await route.fulfill({
        json: path.endsWith("/workspace")
          ? opportunityWorkspace(true, true)
          : opportunity(),
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/companies**",
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      await route.fulfill({
        json:
          path === "/api/v1/companies/company-1"
            ? {
                id: "company-1",
                organisationId: "organisation-1",
                name: "Acme Australia",
                website: null,
                industry: "Technology",
                employeeCount: 120,
                status: "active",
                ownerUserId: "user-1",
                createdAt: "2026-07-01T00:00:00Z",
                updatedAt: "2026-08-14T02:12:00Z",
              }
            : { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/accounts/company-1/brain**",
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/reasoning")) {
        await route.fulfill({
          json: {
            state: "insufficient_history",
            message:
              "A second snapshot is required for longitudinal reasoning.",
            latest: null,
            history: [],
          },
        });
        return;
      }
      if (path.endsWith("/visual-evidence")) {
        await route.fulfill({ json: [] });
        return;
      }
      await route.fulfill({
        json: [
          {
            id: "snapshot-recorded",
            organisationId: "organisation-1",
            companyId: "company-1",
            opportunityId: "opportunity-1",
            meetingId: "meeting-1",
            transcriptVersionId: "transcript-version-recorded",
            createdAt: "2026-08-14T02:13:00Z",
            meetingDate: "2026-08-14T02:00:00Z",
            summaryReference: "summary-recorded",
            buyingSignalsReference: "buying-recorded",
            objectionsReference: "objections-recorded",
            stakeholdersReference: "stakeholders-recorded",
            decisionsReference: "decisions-recorded",
            actionsReference: "actions-recorded",
            risksReference: "risks-recorded",
            questionsReference: "questions-recorded",
            nextBestActionReference: "next-recorded",
            version: 1,
          },
        ],
      });
    },
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/sign-in");
  await page
    .getByRole("link", { name: "Continue with development identity" })
    .click();
  await page.goto("/interactions/interaction-recording/companion");
  await expect(page.getByText("30-second brief")).toBeVisible();
  await page.getByRole("button", { name: "Start interaction" }).click();
  await page.getByRole("button", { name: "Record interaction" }).click();
  await page
    .getByRole("checkbox", { name: /participants have received/i })
    .check();
  await page.getByRole("button", { name: "Start recording" }).click();
  await page.getByRole("button", { name: "Pause" }).click();
  await page.getByRole("button", { name: "Resume" }).click();
  await page.getByRole("button", { name: "Stop and upload" }).click();
  await expect(page.getByText("Transcription is processing.")).toBeVisible();
  await page
    .getByRole("button", { name: "Refresh transcription status" })
    .click();
  await expect(page.getByText("Transcription is ready.")).toBeVisible();
  await expect(
    page.getByText(
      "The customer approved the pilot and confirmed procurement ownership.",
    ),
  ).toHaveCount(0);
  if (process.env.CAPTURE_WO_016_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-016-companion-recording.png",
      fullPage: true,
    });
  }
  if (process.env.CAPTURE_WO_015_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-015-recording-transcription.png",
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Add marker" }).click();
  await page.getByRole("button", { name: "Decision" }).click();
  await expect(page.getByText("Decision marked.")).toBeVisible();
  await page.getByRole("button", { name: "Add photo" }).click();
  await page.getByLabel("Choose an image").setInputFiles({
    name: "recording-whiteboard.png",
    mimeType: "image/png",
    buffer: Buffer.from([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
      0x49, 0x48, 0x44, 0x52,
    ]),
  });
  await page
    .getByRole("checkbox", { name: /authorised to upload this image/i })
    .check();
  await page.getByRole("button", { name: "Upload and prepare review" }).click();
  await expect(page.getByText(/Image saved/i)).toBeVisible();
  for (const prohibited of [
    "providerRequestId",
    "transcriptionRequestId",
    "storageKey",
    "short-lived-test-token",
    "MOCK_TRANSCRIPT",
  ]) {
    await expect(page.getByText(prohibited, { exact: false })).toHaveCount(0);
  }

  await page.getByRole("button", { name: "End interaction" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Fill the gaps while they are fresh",
    }),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: /safely stopped/i }).check();
  await page.getByRole("button", { name: "Start typed debrief" }).click();
  await expect(
    page.getByText("What important outcome might the recording have missed?"),
  ).toBeVisible();
  await page
    .getByLabel("Your answer")
    .fill("Morgan owns the final security review.");
  await page.getByRole("button", { name: "Save answer" }).click();
  await page.getByRole("button", { name: "Review captured evidence" }).click();
  await page
    .getByRole("button", { name: "Finish review and update intelligence" })
    .click();
  await expect(page.getByText("Debrief complete")).toBeVisible();
  await expect(
    page.getByText(
      /Reviewed evidence saved to the interaction and Revenue Brain/i,
    ),
  ).toBeVisible();
  expect(chunkUploadAttempts).toBeGreaterThan(1);
  expect(visuals).toHaveLength(1);
  await page.goto("/meetings/meeting-1");
  await page.getByRole("tab", { name: "Intelligence" }).click();
  await page
    .getByRole("button", { name: "Generate Meeting Intelligence" })
    .click();
  await expect(page.getByText("10 of 10 ready")).toBeVisible();
  await page.goto("/opportunities/opportunity-1");
  await expect(
    page.getByText("Identify the economic buyer.", { exact: true }).first(),
  ).toBeVisible();
  await page.goto("/companies/company-1");
  await expect(page.getByText("Meeting snapshot")).toBeVisible();
  expect(intelligenceGenerated).toBe(true);
});

test("mobile Companion passive path captures a marker and photo before a reviewed debrief", async ({
  page,
}) => {
  let interaction: Record<string, unknown> = interactionRecord({
    id: "interaction-passive",
    title: "Executive renewal lunch",
    interactionType: "executive_lunch",
    opportunityId: "opportunity-1",
    briefState: "completed",
    briefGeneratedAt: "2026-08-14T02:00:00Z",
  });
  const markers: Array<Record<string, unknown>> = [];
  const visuals: Array<Record<string, unknown>> = [];
  let passiveDebrief = debriefSession("collecting", {
    interactionId: "interaction-passive",
  });
  let recordingPostCount = 0;

  await page.route(
    "http://localhost:8000/api/v1/beta/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          featureFlags: {
            aiCompanion: true,
            aiDebrief: true,
            voiceJournal: true,
            visualEvidence: true,
            recordingCapture: true,
          },
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/interactions/interaction-passive**",
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.endsWith("/companion/brief")) {
        await route.fulfill({
          json: companionBrief("executive_lunch", false),
        });
        return;
      }
      if (path.endsWith("/companion/markers")) {
        if (request.method() === "POST") {
          const body = request.postDataJSON() as { markerType: string };
          const marker = {
            id: `passive-marker-${markers.length + 1}`,
            interactionId: "interaction-passive",
            createdByUserId: "user-1",
            markerType: body.markerType,
            recordingOffsetMs: null,
            createdAt: "2026-08-14T02:15:00Z",
          };
          markers.push(marker);
          await route.fulfill({ status: 201, json: marker });
        } else {
          await route.fulfill({ json: markers });
        }
        return;
      }
      if (path.endsWith("/visual-evidence/uploads")) {
        await route.fulfill({
          status: 201,
          json: visualEvidence("uploading", {
            interactionId: "interaction-passive",
            uploadUrl: `${path}/visual-1/content?token=passive-test`,
            uploadExpiresAt: "2026-08-14T02:20:00Z",
          }),
        });
        return;
      }
      if (path.endsWith("/content") && request.method() === "PUT") {
        await route.fulfill({ status: 204 });
        return;
      }
      if (path.endsWith("/visual-evidence/visual-1/complete")) {
        await route.fulfill({
          json: visualEvidence("uploaded", {
            interactionId: "interaction-passive",
          }),
        });
        return;
      }
      if (path.endsWith("/visual-evidence/visual-1/process")) {
        const completedVisual = visualEvidence("completed", {
          interactionId: "interaction-passive",
        });
        visuals.splice(0, visuals.length, completedVisual);
        await route.fulfill({ json: completedVisual });
        return;
      }
      if (path.endsWith("/visual-evidence")) {
        await route.fulfill({ json: visuals });
        return;
      }
      if (path.endsWith("/recordings")) {
        if (request.method() === "POST") recordingPostCount += 1;
        await route.fulfill({ json: [] });
        return;
      }
      if (
        path === "/api/v1/interactions/interaction-passive/start" &&
        request.method() === "POST"
      ) {
        interaction = {
          ...interaction,
          lifecycleStatus: "in_progress",
          actualStartAt: "2026-08-14T02:10:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      if (
        path === "/api/v1/interactions/interaction-passive/complete" &&
        request.method() === "POST"
      ) {
        interaction = {
          ...interaction,
          lifecycleStatus: "completed",
          actualEndAt: "2026-08-14T03:00:00Z",
        };
        await route.fulfill({ json: interaction });
        return;
      }
      if (path.endsWith("/debrief") && request.method() === "POST") {
        await route.fulfill({ status: 201, json: passiveDebrief });
        return;
      }
      if (path.endsWith("/response")) {
        passiveDebrief = debriefSession("collecting", {
          interactionId: "interaction-passive",
          questionCount: 1,
          currentQuestion: {
            status: "complete",
            question: null,
            reason: "The reported outcome is ready for review.",
            target: null,
            priority: null,
          },
          canFinish: true,
          turns: [
            {
              id: "passive-turn-1",
              turnNumber: 1,
              question: passiveDebrief.currentQuestion,
              answerText: "The customer asked for a revised rollout plan.",
              inputMode: "text",
              createdAt: "2026-08-14T03:02:00Z",
            },
          ],
        });
        await route.fulfill({ json: passiveDebrief });
        return;
      }
      if (path.endsWith("/finish")) {
        passiveDebrief = debriefSession("review", {
          interactionId: "interaction-passive",
          currentQuestion: null,
          candidates: [reportedCandidate()],
        });
        await route.fulfill({ json: passiveDebrief });
        return;
      }
      if (path.endsWith("/review")) {
        passiveDebrief = debriefSession("completed", {
          interactionId: "interaction-passive",
          currentQuestion: null,
          candidates: [
            {
              ...reportedCandidate(),
              validationState: "verified",
              userReviewState: "accepted",
              acceptedEvidenceId: "passive-evidence",
            },
          ],
          interactionIntelligenceId: "passive-intelligence",
          revenueBrainSnapshotId: "passive-brain",
          completedAt: "2026-08-14T03:05:00Z",
          acceptedCount: 1,
          rejectedCount: 0,
          interactionUpdated: true,
          revenueBrainUpdated: true,
        });
        await route.fulfill({ json: passiveDebrief });
        return;
      }
      if (path.includes("/debrief/session-1")) {
        await route.fulfill({ json: passiveDebrief });
        return;
      }
      await route.fulfill({ json: interaction });
    },
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/interactions/interaction-passive/companion");
  await page.getByRole("button", { name: "Start interaction" }).click();
  await expect(
    page.getByText(/Passive Companion is recommended/i),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Continue without recording" })
    .click();
  await expect(
    page.getByRole("heading", { name: "No recording or listening" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Add marker" }).click();
  await page.getByRole("button", { name: "Question", exact: true }).click();
  await page.getByRole("button", { name: "Add photo" }).click();
  await page.getByLabel("Choose an image").setInputFiles({
    name: "lunch-whiteboard.png",
    mimeType: "image/png",
    buffer: Buffer.from([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
      0x49, 0x48, 0x44, 0x52,
    ]),
  });
  await page
    .getByRole("checkbox", { name: /authorised to upload this image/i })
    .check();
  await page.getByRole("button", { name: "Upload and prepare review" }).click();
  await expect(page.getByText(/Image saved/i)).toBeVisible();

  await page.getByRole("button", { name: "End interaction" }).click();
  await expect(
    page.getByRole("heading", { name: "Fill the gaps while they are fresh" }),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_016_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-016-companion-passive-after.png",
      fullPage: true,
    });
  }
  await page.getByRole("checkbox", { name: /safely stopped/i }).check();
  await page.getByRole("button", { name: "Start typed debrief" }).click();
  await expect(page.getByText("How did it go?")).toBeVisible();
  await page
    .getByLabel("Your answer")
    .fill("The customer asked for a revised rollout plan.");
  await page.getByRole("button", { name: "Save answer" }).click();
  await page.getByRole("button", { name: "Review captured evidence" }).click();
  await page
    .getByRole("button", { name: "Finish review and update intelligence" })
    .click();
  await expect(page.getByText("Debrief complete")).toBeVisible();
  await expect(
    page.getByText(
      /Reviewed evidence saved to the interaction and Revenue Brain/i,
    ),
  ).toBeVisible();
  expect(recordingPostCount).toBe(0);
  expect(markers).toHaveLength(1);
  expect(visuals).toHaveLength(1);
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
  await expect(page.getByText("0 of 10 ready")).toBeVisible();

  await page
    .getByRole("button", { name: "Generate Meeting Intelligence" })
    .click();
  await expect(
    page.getByText(/Generating 8 sections|8 sections queued/),
  ).toBeVisible();
  await expect(page.getByText("10 of 10 ready")).toBeVisible({
    timeout: 12_000,
  });
  await expect(
    page
      .getByRole("article", { name: "Buying Signals & Deal Momentum" })
      .getByText("Strong Positive", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/win probability/i)).toHaveCount(0);
  await expect(page.getByText(/deal score/i)).toHaveCount(0);
  await expect(
    page
      .getByRole("article", { name: "Objections & Competitive Signals" })
      .getByText("Competitor X", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Objections & Competitive Signals" })
      .getByText("Current meeting objection pressure"),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Stakeholders" })
      .getByText("Jane Smith", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Stakeholders" })
      .getByText("Likely Champion", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/relationship graph/i)).toHaveCount(0);
  await expect(page.getByText(/crm action/i)).toHaveCount(0);
  await expect(
    page
      .getByRole("article", { name: "Next Best Action" })
      .getByText("Identify the economic buyer.", { exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Next Best Action" })
      .getByText("94%", { exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page.getByRole("article", { name: "Next Best Action" }).getByRole("button"),
  ).toHaveCount(0);
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
  if (process.env.CAPTURE_WO_006D_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-006d-next-best-action.png",
      fullPage: true,
    });
  } else if (process.env.CAPTURE_WO_006C_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-006c-stakeholder-intelligence.png",
      fullPage: true,
    });
  } else if (process.env.CAPTURE_WO_006B_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-006b-objections-competitive-signals.png",
      fullPage: true,
    });
  } else if (process.env.CAPTURE_WO_006A_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-006a-buying-signals-deal-momentum.png",
      fullPage: true,
    });
  } else if (process.env.CAPTURE_WO_005_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-005-unified-meeting-intelligence.png",
      fullPage: true,
    });
  }

  await page.reload();
  await page.getByRole("tab", { name: "Intelligence" }).click();
  await expect(page.getByText("10 of 10 ready")).toBeVisible();
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

test("opportunity workspace persists an associated meeting and composes stored intelligence", async ({
  page,
}) => {
  let associated = false;
  let reasoningGenerated = false;

  await page.route(
    "http://localhost:8000/api/v1/opportunities**",
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.endsWith("/workspace")) {
        await route.fulfill({
          json: opportunityWorkspace(associated, reasoningGenerated),
        });
        return;
      }
      if (path.endsWith("/brain/reasoning") && request.method() === "POST") {
        reasoningGenerated = true;
        await route.fulfill({
          json: {
            ...opportunityReasoning("completed"),
            created: true,
          },
        });
        return;
      }
      if (path.endsWith("/opportunity-1")) {
        await route.fulfill({ json: opportunity() });
        return;
      }
      if (request.method() === "POST") {
        await route.fulfill({ status: 201, json: opportunity() });
        return;
      }
      await route.fulfill({
        json: { items: [], page: 1, pageSize: 20, total: 0, pages: 0 },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/companies**",
    async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              id: "company-1",
              organisationId: "organisation-1",
              name: "Acme Australia",
              website: null,
              industry: null,
              employeeCount: null,
              status: "prospect",
              ownerUserId: "user-1",
              createdAt: "2026-07-20T00:00:00Z",
              updatedAt: "2026-07-20T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 100,
          total: 1,
          pages: 1,
        },
      });
    },
  );
  await page.route("http://localhost:8000/api/v1/meetings**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/opportunity") && request.method() === "PATCH") {
      associated = true;
      await route.fulfill({ json: opportunityMeeting() });
      return;
    }
    if (path.endsWith("/participants") || path.endsWith("/history")) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith("/transcript")) {
      await route.fulfill({
        json: {
          id: "transcript-1",
          organisationId: "organisation-1",
          meetingId: "meeting-1",
          rawText: "Synthetic authorised test transcript.",
          language: "en-AU",
          version: 1,
          source: "manual",
          createdAt: "2026-07-20T00:00:00Z",
          updatedAt: "2026-07-20T00:00:00Z",
        },
      });
      return;
    }
    if (path.endsWith("/meeting-1")) {
      await route.fulfill({ json: opportunityMeeting() });
      return;
    }
    await route.fulfill({
      json: {
        items: [
          {
            ...opportunityMeeting(),
            opportunityId: associated ? "opportunity-1" : null,
          },
        ],
        page: 1,
        pageSize: 100,
        total: 1,
        pages: 1,
      },
    });
  });

  await page.goto("/opportunities");
  await expect(
    page.getByRole("heading", { name: "Opportunities", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Create opportunity" }).first().click();
  await page.getByLabel("Company").selectOption("company-1");
  await page.getByLabel("Opportunity name").fill("Platform expansion");
  await page.getByLabel("Stage").selectOption("proposal");
  await page.getByLabel("Estimated value").fill("125000.50");
  await page.getByLabel("Currency").selectOption("AUD");
  await page.getByLabel("Expected close date").fill("2026-09-30");
  await page.getByRole("button", { name: "Create opportunity" }).click();

  await expect(
    page.getByRole("heading", { name: "Platform expansion" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No meetings associated" }),
  ).toBeVisible();
  await page.getByLabel("Meeting", { exact: true }).selectOption("meeting-1");
  await page.getByRole("button", { name: "Associate meeting" }).click();
  await expect(
    page.getByRole("heading", { name: "Latest Next Best Action" }),
  ).toBeVisible();
  await expect(
    page.getByText("Identify the economic buyer.", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Expansion review" }),
  ).toHaveAttribute("href", "/meetings/meeting-1");
  await expect(
    page.getByRole("heading", { name: "Longitudinal Changes" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Generate changes" }).click();
  await expect(
    page.getByText("Champion influence strengthened.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "15 July 2026" }),
  ).toHaveAttribute("href", "/meetings/meeting-previous");
  if (process.env.CAPTURE_WO_008B_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-008b-revenue-brain-reasoning.png",
      fullPage: true,
    });
  }

  await page.getByRole("button", { name: "Refresh workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Latest Next Best Action" }),
  ).toBeVisible();
  for (const prohibited of [
    "probability",
    "forecast",
    "provider",
    "prompt",
    "worker",
  ]) {
    await expect(page.getByText(new RegExp(prohibited, "i"))).toHaveCount(0);
  }

  await page
    .getByRole("link", { name: "Open latest meeting intelligence" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Pilot readiness review" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Platform expansion" }),
  ).toHaveAttribute("href", "/opportunities/opportunity-1");
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

function opportunity() {
  return {
    id: "opportunity-1",
    organisationId: "organisation-1",
    companyId: "company-1",
    name: "Platform expansion",
    stage: "proposal",
    status: "open",
    estimatedValue: "125000.50",
    currency: "AUD",
    expectedCloseDate: "2026-09-30",
    ownerUserId: "user-1",
    description: null,
    createdAt: "2026-07-20T00:00:00Z",
    updatedAt: "2026-07-24T00:00:00Z",
  };
}

function opportunityMeeting() {
  return {
    ...meeting(),
    title: "Pilot readiness review",
    companyId: "company-1",
    opportunityId: "opportunity-1",
    updatedAt: "2026-07-24T00:00:00Z",
  };
}

function opportunityWorkspace(
  hasMeeting: boolean,
  reasoningGenerated: boolean,
) {
  const summary = {
    id: "meeting-1",
    title: "Expansion review",
    meetingDate: "2026-07-20T00:00:00Z",
    status: "completed",
    companyId: "company-1",
    companyName: "Acme Australia",
    participantCount: 2,
    transcriptAvailable: true,
    transcriptVersion: 1,
    intelligenceReadiness: "ready",
    intelligenceSectionsAvailable: 10,
    updatedAt: "2026-07-24T00:00:00Z",
  };
  return {
    opportunity: {
      ...opportunity(),
      companyName: "Acme Australia",
      ownerName: "Alex Morgan",
    },
    latestMeeting: hasMeeting ? summary : null,
    recentMeetings: hasMeeting ? [summary] : [],
    intelligence: hasMeeting ? workspace("completed") : null,
    intelligenceSectionsAvailable: hasMeeting ? 10 : 0,
    reasoning: hasMeeting
      ? opportunityReasoning(reasoningGenerated ? "completed" : "not_generated")
      : opportunityReasoning("insufficient_history"),
    partialData: false,
    generatedAt: "2026-07-24T00:00:08Z",
  };
}

function opportunityReasoning(
  state: "insufficient_history" | "not_generated" | "completed",
) {
  const latest =
    state === "completed"
      ? {
          id: "reasoning-1",
          companyId: "company-1",
          opportunityId: "opportunity-1",
          reasoningVersion: 1,
          createdAt: "2026-07-24T00:00:08Z",
          content: {
            scope: "opportunity",
            fromSnapshotId: "snapshot-previous",
            toSnapshotId: "snapshot-latest",
            fromMeetingId: "meeting-previous",
            toMeetingId: "meeting-1",
            fromMeetingDate: "2026-07-15",
            toMeetingDate: "2026-07-20",
            changes: [
              {
                changeType: "champion_strengthened",
                direction: "positive",
                importance: "high",
                title: "Champion influence strengthened",
                description:
                  "The identified champion moved from medium to high influence.",
                confidence: 0.91,
                sourceCapabilities: ["stakeholder_intelligence"],
                evidence: [
                  {
                    snapshotId: "snapshot-latest",
                    artefactId: "stakeholder-artefact-latest",
                    artefactType: "stakeholder_intelligence",
                    entityKey: "stakeholder:fixture",
                    field: "influence",
                    value: "high",
                  },
                ],
              },
            ],
            summary: "Champion influence strengthened.",
            confidence: 0.91,
          },
        }
      : null;
  return {
    state,
    message:
      state === "insufficient_history"
        ? "Revenue Brain needs at least two completed meeting snapshots before it can identify changes."
        : state === "not_generated"
          ? "Longitudinal reasoning has not been generated for the latest snapshots."
          : "Longitudinal reasoning is available.",
    latest,
    history: latest ? [latest] : [],
  };
}

function dataNotice(acknowledged: boolean) {
  return {
    version: 1,
    acknowledged,
    acknowledgedAt: acknowledged ? "2026-07-25T00:00:00Z" : null,
    providerMode: "mock",
    externalProcessingEnabled: false,
    notice: [
      "You must have authority to add or process this meeting content.",
      "Mock mode keeps processing internal.",
      "Generated intelligence may contain errors and must be reviewed.",
    ],
  };
}

function betaAdminOverview() {
  return {
    organisation: {
      id: "organisation-1",
      name: "Synthetic Beta Organisation",
      slug: "synthetic-beta-organisation",
    },
    members: [
      {
        user: {
          id: "user-1",
          displayName: "Alex Morgan",
          email: "alex@example.test",
        },
        role: "admin",
        status: "active",
        joinedAt: "2026-07-25T00:00:00Z",
      },
    ],
    retention: { policy: "days_90", defaultApplied: true },
    noticeVersion: 1,
    acknowledgementCount: 1,
    activeMemberCount: 1,
    featureFlags: {
      openaiProvider: false,
      revenueBrain: true,
      opportunityWorkspace: true,
      aiCompanion: true,
      aiDebrief: true,
      voiceJournal: true,
      visualEvidence: false,
      presentationMode: false,
      recordingCapture: false,
      transcription: false,
      autoGenerateIntelligenceAfterTranscription: false,
      dataExport: true,
      organisationDeletion: false,
    },
    usage: {
      date: "2026-07-25",
      generations: 0,
      generationLimit: 100,
      providerRequests: 0,
      providerRequestLimit: 150,
      estimatedCostAvailable: false,
    },
    recentEvents: [],
    dataRequests: [],
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
  const ready = stage === "completed" ? 10 : contentReady ? 8 : 0;
  const processing = stage === "extractions" ? 8 : 0;
  const queued = stage === "email" ? 2 : 0;
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
      notGenerated: 10 - ready - queued - processing,
      total: 10,
      summary:
        stage === "not_started"
          ? "0 of 10 ready"
          : stage === "extractions"
            ? "Generating 8 sections"
            : stage === "prerequisites"
              ? "8 of 10 ready"
              : stage === "email"
                ? "2 sections queued"
                : "10 of 10 ready",
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
    buyingSignals: capability(
      extractionState,
      contentReady
        ? {
            signals: [
              {
                signalType: "timeline_confirmed",
                polarity: "positive",
                strength: "strong",
                confidence: 0.94,
                evidence: "The customer confirmed a September pilot start.",
              },
            ],
            overallMomentum: "strong_positive",
            momentumSummary:
              "The current meeting shows strong positive momentum from the extracted signals.",
            confidence: 0.9,
          }
        : null,
    ),
    objectionsCompetitiveSignals: capability(
      extractionState,
      contentReady
        ? {
            objections: [
              {
                objection:
                  "The customer believes implementation needs too many resources.",
                category: "implementation",
                status: "unresolved",
                strength: "strong",
                owner: "Customer IT",
                confidence: 0.93,
                evidence:
                  "Customer IT said it could not support the proposed rollout.",
              },
            ],
            competitors: [
              {
                name: "Competitor X",
                position: "stronger",
                confidence: 0.88,
                evidence:
                  "The competitor already integrates with the customer's stack.",
              },
            ],
            overallObjectionPressure: "high",
            summary:
              "Implementation capacity and Competitor X create meaningful pressure.",
          }
        : null,
    ),
    stakeholderIntelligence: capability(
      extractionState,
      contentReady
        ? {
            stakeholders: [
              {
                name: "Jane Smith",
                organisation: "Customer",
                role: "champion",
                influence: "high",
                stance: "supportive",
                engagement: "active",
                confidence: 0.93,
                evidence:
                  "Jane advocated for the solution and committed to presenting it internally.",
              },
            ],
            roleCoverage: {
              economicBuyer: "not_identified",
              decisionMaker: "unclear",
              champion: "identified",
              technicalBuyer: "not_discussed",
              procurement: "not_discussed",
              legalSecurity: "not_discussed",
            },
            stakeholderSummary:
              "A likely champion is present, but the economic buyer remains unidentified.",
            confidence: 0.89,
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
    nextBestAction: capability(
      stage === "completed"
        ? "completed"
        : stage === "email"
          ? "queued"
          : contentReady
            ? "not_generated"
            : "unavailable",
      stage === "completed"
        ? {
            overallRecommendation: "Identify the economic buyer.",
            priority: "high",
            confidence: 0.94,
            reasoning: [
              "Buying Signals: decision_maker_missing.",
              "Stakeholders: economic_buyer:not_identified.",
            ],
            recommendedActions: [
              {
                action: "Identify the economic buyer.",
                reason:
                  "Buying Signals: decision_maker_missing. Stakeholders: economic_buyer:not_identified.",
                priority: "high",
                confidence: 0.94,
                dependsOn: ["buying_signals", "stakeholders"],
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
            "buying_signals",
            "objections_competitive_signals",
            "stakeholder_intelligence",
            "decisions",
            "action_items",
            "risks_blockers",
            "open_questions",
          ]
        : stage === "email"
          ? ["next_best_action", "follow_up_email"]
          : [],
    reusedCapabilities: [],
  };
}

function interactionRecord(overrides: Record<string, unknown>) {
  return {
    id: "interaction-1",
    organisationId: "organisation-1",
    companyId: "company-1",
    opportunityId: null,
    meetingId: null,
    interactionType: "manual_interaction",
    lifecycleStatus: "planned",
    title: "Customer interaction",
    scheduledStartAt: "2026-08-04T01:00:00Z",
    scheduledEndAt: null,
    actualStartAt: null,
    actualEndAt: null,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    createdByUserId: "user-1",
    briefState: "not_generated",
    briefGeneratedAt: null,
    createdAt: "2026-07-26T00:00:00Z",
    updatedAt: "2026-07-26T00:00:00Z",
    ...overrides,
  };
}

function reportedCandidate() {
  return {
    id: "candidate-1",
    evidenceCategory: "budget",
    statement: "Jordan confirmed the budget.",
    originalStatement: "Jordan confirmed the budget.",
    origin: "salesperson_reported",
    sourceLabel: "Reported by you",
    supportClassification: "reported",
    validationState: "unreviewed",
    userReviewState: "pending",
    sourceCaptureSessionId: "session-1",
    evidenceFragmentId: "fragment-1",
    acceptedEvidenceId: null,
    entityReference: null,
    explicitlyReportedAt: null,
    edited: false,
  };
}

function visualCandidate(overrides: Record<string, unknown> = {}) {
  return {
    id: "candidate-visual-1",
    category: "customer_request",
    statement: "Customer requested a security workshop.",
    originalStatement: "Customer requested a security workshop.",
    sourceVisualId: "visual-1",
    sourceOwnership: "customer_created",
    origin: "ai_inferred",
    supportClassification: "direct",
    validationState: "unreviewed",
    reviewState: "pending",
    conflictState: "not_assessed",
    confidenceClass: "low",
    evidenceRegion: { x: 0, y: 0, width: 1, height: 1 },
    relatedEntity: null,
    extractedTextSnippet: null,
    acceptedEvidenceId: null,
    edited: false,
    ...overrides,
  };
}

function visualEvidence(
  processingStatus: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id: "visual-1",
    interactionId: "interaction-visual",
    captureSessionId: "visual-1",
    visualType: "whiteboard",
    sourceOwnership: "customer_created",
    contextLabel: "Customer requested a security workshop",
    filename: "customer-question.png",
    mimeType: "image/png",
    byteSize: 68,
    width: 1,
    height: 1,
    checksumSha256: "a".repeat(64),
    capturedAt: "2026-08-14T02:00:00Z",
    processingStatus,
    processingAttempts: processingStatus === "uploading" ? 0 : 1,
    failureCode: null,
    providerMode: "mock",
    externalProcessing: false,
    candidates: processingStatus === "review" ? [visualCandidate()] : [],
    downloadUrl: null,
    interactionIntelligenceId: null,
    revenueBrainSnapshotId: null,
    createdAt: "2026-08-14T02:00:00Z",
    updatedAt: "2026-08-14T02:00:00Z",
    ...overrides,
  };
}

function visualIntelligencePayload() {
  return {
    id: "intelligence-visual-1",
    interactionId: "interaction-visual",
    generatedAt: "2026-08-14T02:10:00Z",
    sourceLabel: "customer whiteboard",
    visualType: "whiteboard",
    items: [
      {
        evidenceId: "evidence-visual-accepted",
        category: "customer_request",
        statement: "Customer requested a reviewed security workshop.",
        origin: "ai_inferred",
        sourceOwnership: "customer_created",
        supportClassification: "direct",
        sourceLabel: "customer whiteboard",
        validationState: "verified",
        conflictState: "not_assessed",
      },
    ],
  };
}

function debriefSession(
  lifecycleStatus: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id: "session-1",
    interactionId: "interaction-debrief",
    captureType: "ai_debrief",
    lifecycleStatus,
    questionCount: 0,
    maxQuestions: 6,
    currentQuestion: {
      status: "ask",
      question: "How did it go?",
      reason: "Start naturally.",
      target: "other",
      priority: "high",
    },
    canFinish: false,
    finishedEarly: false,
    turns: [],
    candidates: [],
    interactionIntelligenceId: null,
    revenueBrainSnapshotId: null,
    startedAt: "2026-08-14T02:01:00Z",
    updatedAt: "2026-08-14T02:01:00Z",
    completedAt: null,
    ...overrides,
  };
}

function emptyBriefResponse() {
  return {
    state: "not_generated",
    generationAvailable: true,
    unavailableReason: null,
    safeMessage: null,
    brief: null,
    generatedAt: null,
    reviewed: false,
    reviewedAt: null,
    priorVersions: [],
    sourceLabels: [],
  };
}

function companionBrief(interactionType: string, reviewed: boolean) {
  const presentation = interactionType === "presentation";
  const phone = interactionType === "phone_call";
  return {
    ...emptyBriefResponse(),
    state: "completed",
    generatedAt: "2026-08-14T02:00:00Z",
    reviewed,
    reviewedAt: reviewed ? "2026-08-14T02:05:00Z" : null,
    sourceLabels: [
      "Interaction details",
      "Opportunity record",
      "Prior validated Meeting Intelligence",
    ],
    brief: {
      interactionId: `interaction-${presentation ? "presentation" : phone ? "phone" : "face"}`,
      interactionType,
      briefVersion: 1,
      headline: presentation
        ? "Validate audience priorities and agree the next validation step."
        : phone
          ? "Use the call to agree one useful next step."
          : "Align on the pilot outcome and agree a clear next step.",
      accountContext:
        "Southern Cross Operations has an evaluation-stage pilot opportunity with validated prior context.",
      recentChanges: [
        {
          change: "Procurement entered the process.",
          importance: "high",
          source: "revenue_brain",
        },
      ],
      objectives: [
        {
          objective: "Clarify procurement ownership.",
          priority: "high",
          reason: "The approval path remains unresolved.",
        },
      ],
      questionsToAsk: [
        {
          question: "Who will own the procurement process from here?",
          purpose: "Clarify the approval path.",
          priority: "high",
        },
      ],
      stakeholderFocus: [
        {
          name: "Alex Morgan",
          role: "champion",
          focus: "Confirm current priorities and the next introduction.",
        },
      ],
      openCommitments: [
        {
          commitment: "Provide the security summary.",
          owner: "Revenue team",
          dueDate: null,
        },
      ],
      risksToWatch: [
        { risk: "Security review may delay progress.", severity: "high" },
      ],
      successCriteria: ["A next step, owner and timing are agreed."],
      interactionGuidance: presentation
        ? "Treat seller-prepared material as context, not customer evidence, and close with a validation step."
        : phone
          ? "Keep the call concise, lead with the objective and close with a confirmed next step."
          : "Keep the objective, stakeholder priorities and success criteria easy to scan before the meeting.",
      confidence: 0.82,
      companyName: "Southern Cross Operations",
      opportunityName: "Evaluation-stage pilot",
      participants: [{ name: "Alex Morgan", role: "champion" }],
      nextBestAction: "Confirm procurement ownership.",
    },
  };
}
