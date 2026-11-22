import { expect, test, type Page } from "@playwright/test";

const interactionId = "interaction-daily";

function meResponse() {
  return { organisation: { id: "organisation-1" } };
}

function dailyResponse(overrides: Record<string, unknown> = {}) {
  const next = {
    id: interactionId,
    title: "Northstar technical review",
    companyId: "company-daily",
    companyName: "Northstar Facilities",
    opportunityId: null,
    opportunityName: null,
    participantNames: ["Jordan Lee"],
    interactionType: "online_meeting",
    lifecycleStatus: "planned",
    startsAt: "2026-11-02T00:00:00Z",
    preparationState: "not_prepared",
    context:
      "Clarify the security review and the unresolved implementation questions.",
    ctaLabel: "Prepare",
    href: `/conversations/${interactionId}#preparation`,
  };
  return {
    generatedAt: "2026-10-31T00:00:00Z",
    localDate: "2026-10-31",
    timezone: "Australia/Sydney",
    userDisplayName: "Alex Morgan",
    topPriority: null,
    nextInteraction: next,
    todayInteractions: [
      next,
      {
        ...next,
        id: "interaction-later",
        title: "Commercial follow-up call",
        interactionType: "phone_call",
        startsAt: "2026-11-02T03:00:00Z",
        preparationState: "prepared",
        context: "Return to the agreed pilot scope.",
        href: "/conversations/interaction-later#preparation",
      },
    ],
    totalTodayInteractions: 2,
    actions: {
      attentionCount: 1,
      overdueCount: 1,
      dueTodayCount: 0,
      pendingReviewCount: 1,
      approvedOpenCount: 0,
      truncated: false,
      items: [
        {
          id: "action-daily",
          title: "Send the agreed security summary",
          opportunityId: "opportunity-daily",
          opportunityName: "Synthetic evaluation",
          companyName: "Northstar Facilities",
          priority: "high",
          reviewStatus: "proposed",
          timing: "overdue",
          dueAt: "2026-10-30T01:00:00Z",
          state: "needs_review",
          stateLabel: "Needs review",
          ctaLabel: "Review",
          href: "/opportunities/opportunity-daily#recommended-actions",
        },
      ],
    },
    privateFollowUps: {
      attentionCount: 1,
      items: [
        {
          interactionId: "interaction-private-follow-up",
          interactionTitle: "Founder coffee follow-up",
          companyName: null,
          updatedAt: "2026-10-30T02:00:00Z",
          ctaLabel: "Review",
          href: "/conversations/interaction-private-follow-up?view=review#follow-up",
        },
      ],
      truncated: false,
    },
    dealAttention: { attentionCount: 0, items: [], truncated: false },
    pipeline: {
      state: "empty",
      openOpportunityCount: 0,
      unvaluedOpportunityCount: 0,
      currencyCount: 0,
      currencies: [],
      safeMessage: "No pipeline context is required for conversations.",
    },
    recommendations: [],
    availability: {
      interactions: true,
      actions: true,
      privateFollowUps: true,
      dealAttention: true,
      pipeline: true,
      recommendations: true,
      methodology: true,
      revenueBrain: true,
      targets: false,
      forecast: false,
    },
    hasOpportunities: false,
    caughtUp: false,
    ...overrides,
  };
}

function recentPage() {
  return {
    organisationId: "organisation-1",
    items: [
      {
        id: "interaction-recent",
        organisationId: "organisation-1",
        companyId: "company-daily",
        opportunityId: null,
        contactId: null,
        meetingId: null,
        eventId: null,
        interactionType: "manual_interaction",
        lifecycleStatus: "completed",
        title: "Founder coffee notes",
        scheduledStartAt: null,
        scheduledEndAt: null,
        actualStartAt: "2026-10-29T00:00:00Z",
        actualEndAt: "2026-10-29T00:30:00Z",
        timezone: "Australia/Sydney",
        creationOrigin: "manual",
        callDirection: null,
        callOutcome: null,
        meetingPlatform: null,
        meetingUrl: null,
        externalMeetingId: null,
        captureSource: null,
        ingestionState: null,
        durationSeconds: 1800,
        captureMethods: ["debrief"],
        intelligenceState: "ready",
        recordingAvailable: false,
        createdByUserId: "user-1",
        briefState: "unavailable",
        briefGeneratedAt: null,
        createdAt: "2026-10-29T00:00:00Z",
        updatedAt: "2026-10-29T00:30:00Z",
      },
    ],
    page: 1,
    pageSize: 6,
    total: 1,
    pages: 1,
  };
}

function accountPage() {
  return {
    organisationId: "organisation-1",
    items: [
      {
        id: "company-daily",
        organisationId: "organisation-1",
        name: "Northstar Facilities",
        website: "https://northstar.example.test",
        industry: "Facilities",
        location: "Sydney",
        employeeCount: 120,
        status: "prospect",
        ownerUserId: "user-1",
        archivedAt: null,
        createdAt: "2026-10-29T00:00:00Z",
        updatedAt: "2026-10-29T00:30:00Z",
      },
    ],
    page: 1,
    pageSize: 8,
    total: 1,
    pages: 1,
  };
}

async function routeHome(page: Page, day = dailyResponse()) {
  await page.route("http://localhost:8000/api/v1/me", async (route) => {
    await route.fulfill({ json: meResponse() });
  });
  await page.route("http://localhost:8000/api/v1/daily**", async (route) => {
    await route.fulfill({ json: day });
  });
  await page.route(
    "http://localhost:8000/api/v1/interactions**",
    async (route) => {
      await route.fulfill({ json: recentPage() });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/companies**",
    async (route) => {
      await route.fulfill({ json: accountPage() });
    },
  );
}

test("Home keeps the next conversation, follow-up and memory central", async ({
  page,
}) => {
  await routeHome(page);
  await page.goto("/dashboard");

  await expect(
    page.getByRole("heading", { name: /Good .*Alex/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Northstar technical review" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Prepare now" })).toHaveAttribute(
    "href",
    `/conversations/${interactionId}#preparation`,
  );
  await expect(
    page.getByRole("heading", { name: "Follow-ups needing attention" }),
  ).toBeVisible();
  await expect(page.getByText("Founder coffee follow-up")).toBeVisible();
  const followUps = page.getByRole("list", {
    name: "Follow-ups needing attention",
  });
  await expect(followUps.getByRole("listitem")).toHaveCount(2);
  await expect(followUps.getByRole("listitem").nth(0)).toContainText(
    "Founder coffee follow-up",
  );
  await expect(followUps.getByRole("listitem").nth(1)).toContainText(
    "Send the agreed security summary",
  );
  await expect(
    followUps.getByRole("link", { name: "Review private draft" }),
  ).toHaveAttribute(
    "href",
    "/conversations/interaction-private-follow-up?view=review#follow-up",
  );
  await expect(
    page.getByRole("link", { name: /Founder coffee notes/ }),
  ).toHaveAttribute("href", "/conversations/interaction-recent");

  const navigation = page.getByRole("navigation", {
    name: "Main navigation",
  });
  await expect(navigation.getByRole("link")).toHaveCount(6);
  for (const label of ["Home", "Conversations", "Knowledge", "Frameworks"]) {
    await expect(navigation.getByRole("link", { name: label })).toBeVisible();
  }
  await expect(navigation.getByRole("link", { name: "Accounts" })).toHaveCount(
    0,
  );
  await expect(navigation.getByRole("link", { name: "Pipeline" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("heading", { name: /forecast|pipeline/i }),
  ).toHaveCount(0);

  if (process.env.CAPTURE_CONVERSATION_INTELLIGENCE_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/conversation-intelligence-home-desktop.png",
      fullPage: true,
    });
  }
  if (process.env.CAPTURE_PRIVATE_FOLLOWUP_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/private-followup-home.png",
      fullPage: true,
    });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = page.getByRole("navigation", {
    name: "Mobile navigation",
  });
  await expect(mobile.getByRole("link")).toHaveCount(4);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  if (process.env.CAPTURE_CONVERSATION_INTELLIGENCE_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/conversation-intelligence-home-mobile.png",
      fullPage: true,
    });
  }
});

test("reviewing a private follow-up removes only its metadata from Home", async ({
  page,
}) => {
  const privateDraft =
    "Private sentinel: send the founder the agreed implementation summary.";
  let workspace = {
    exists: true,
    ownerUserId: "user-1",
    lockVersion: 3,
    liveNotes: "",
    enhancedNotes: "",
    followUpDraft: privateDraft,
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
    updatedAt: "2026-10-30T02:00:00Z",
  };
  const interaction = {
    id: "interaction-private-follow-up",
    organisationId: "organisation-1",
    companyId: null,
    opportunityId: null,
    contactId: null,
    meetingId: null,
    eventId: null,
    interactionType: "manual_interaction",
    lifecycleStatus: "completed",
    title: "Founder coffee follow-up",
    scheduledStartAt: null,
    scheduledEndAt: null,
    actualStartAt: "2026-10-30T01:00:00Z",
    actualEndAt: "2026-10-30T01:30:00Z",
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    callDirection: null,
    callOutcome: null,
    meetingPlatform: null,
    meetingUrl: null,
    externalMeetingId: null,
    captureSource: null,
    ingestionState: null,
    durationSeconds: 1800,
    captureMethods: ["debrief"],
    intelligenceState: "ready",
    recordingAvailable: false,
    createdByUserId: "user-1",
    briefState: "unavailable",
    briefGeneratedAt: null,
    createdAt: "2026-10-30T01:00:00Z",
    updatedAt: "2026-10-30T02:00:00Z",
  };

  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (path === "/api/v1/me") {
      await route.fulfill({ json: meResponse() });
      return;
    }
    if (path === "/api/v1/daily") {
      const privateFollowUps = workspace.followUpReviewed
        ? { attentionCount: 0, items: [], truncated: false }
        : dailyResponse().privateFollowUps;
      await route.fulfill({ json: dailyResponse({ privateFollowUps }) });
      return;
    }
    if (path === "/api/v1/interactions") {
      await route.fulfill({ json: recentPage() });
      return;
    }
    if (path === "/api/v1/companies") {
      await route.fulfill({
        json: {
          organisationId: "organisation-1",
          items: [],
          total: 0,
          page: 1,
          pageSize: 6,
          pages: 0,
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
            liveInteractionIntelligence: false,
          },
        },
      });
      return;
    }
    if (
      path ===
      "/api/v1/interactions/interaction-private-follow-up/personal-workspace"
    ) {
      if (request.method() === "PUT") {
        workspace = {
          ...workspace,
          ...request.postDataJSON(),
          exists: true,
          lockVersion: workspace.lockVersion + 1,
          updatedAt: "2026-10-30T02:05:00Z",
        };
      }
      await route.fulfill({ json: workspace });
      return;
    }
    if (path.endsWith("/conversation-memory")) {
      await route.fulfill({
        json: {
          organisationId: "organisation-1",
          state: "not_configured",
          safeMessage: "No framework is selected.",
          definition: null,
          assignment: {
            interactionId: "interaction-private-follow-up",
            thread: null,
            lockVersion: 0,
            confirmationKind: null,
            confirmedByUserId: null,
            confirmedAt: null,
          },
          suggestions: [],
          currentConversation: null,
          confirmedThread: null,
          confirmedInitiativeHistory: {
            items: [],
            total: 0,
            truncated: false,
          },
          generatedAt: "2026-10-30T02:00:00Z",
        },
      });
      return;
    }
    if (path === "/api/v1/conversation-threads") {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith("/companion/brief")) {
      await route.fulfill({
        json: {
          interactionId: "interaction-private-follow-up",
          state: "unavailable",
          generationAvailable: false,
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
    if (path === "/api/v1/interactions/interaction-private-follow-up") {
      await route.fulfill({ json: interaction });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { code: "not_found", message: "Not part of this test." },
    });
  });

  await page.goto("/dashboard");
  await expect(page.getByText("Founder coffee follow-up")).toBeVisible();
  await expect(page.getByText(privateDraft)).toHaveCount(0);

  await page.getByRole("link", { name: "Review private draft" }).click();
  await expect(page.getByLabel("Private follow-up draft")).toHaveValue(
    privateDraft,
  );
  await expect(page.getByText("Review status: Needs review")).toBeVisible();
  await page.getByRole("button", { name: "Mark reviewed" }).click();
  await expect(page.getByText("Review status: Reviewed")).toBeVisible();
  if (process.env.CAPTURE_FOLLOW_UP_REVIEW_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/private-follow-up-reviewed.png",
      fullPage: true,
    });
  }

  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Home" })
    .click();
  await expect(page.getByText("Founder coffee follow-up")).toHaveCount(0);
  await expect(page.getByText(privateDraft)).toHaveCount(0);
});

test("Home starts with knowledge or a conversation without CRM setup", async ({
  page,
}) => {
  const base = dailyResponse();
  await routeHome(
    page,
    dailyResponse({
      nextInteraction: null,
      todayInteractions: [],
      totalTodayInteractions: 0,
      actions: { ...base.actions, attentionCount: 0, items: [] },
      privateFollowUps: {
        attentionCount: 0,
        items: [],
        truncated: false,
      },
      caughtUp: true,
    }),
  );
  await page.goto("/dashboard");

  await expect(
    page.getByRole("heading", { name: "Nothing is scheduled yet." }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Add conversation" }),
  ).toHaveAttribute("href", "/conversations/new");
  await expect(
    page.getByRole("link", { name: "Set up company knowledge" }),
  ).toHaveAttribute("href", "/knowledge");
  await expect(page.getByText(/create an opportunity/i)).toHaveCount(0);
  await expect(
    page.getByText("No follow-ups need attention right now."),
  ).toBeVisible();
});

test("Home keeps available relationship memory when Daily is unavailable", async ({
  page,
}) => {
  await page.route("http://localhost:8000/api/v1/me", async (route) => {
    await route.fulfill({ json: meResponse() });
  });
  await page.route("http://localhost:8000/api/v1/daily**", async (route) => {
    await route.fulfill({
      status: 503,
      json: {
        code: "persistence_unavailable",
        message: "Conversation history is temporarily unavailable.",
        requestId: "request-home-error",
      },
    });
  });
  await page.route(
    "http://localhost:8000/api/v1/interactions**",
    async (route) => {
      await route.fulfill({ json: recentPage() });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/companies**",
    async (route) => {
      await route.fulfill({ json: accountPage() });
    },
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dashboard");

  await expect(
    page.getByRole("heading", { name: "Conversation workspace" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      /Today's schedule and follow-ups are temporarily unavailable/u,
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Founder coffee notes/u }),
  ).toHaveAttribute("href", "/conversations/interaction-recent");
  await expect(
    page.getByRole("link", {
      name: /Northstar Facilities.*conversation memory/u,
    }),
  ).toHaveAttribute(
    "href",
    "/conversations/accounts/company-daily#conversations",
  );
  await expect(
    page.getByRole("button", { name: "Try Daily again" }),
  ).toBeVisible();
  await expect(page.locator('section[role="alert"]')).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Upcoming conversations" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Follow-ups needing attention" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Conversation history is temporarily unavailable."),
  ).toHaveCount(0);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
});
