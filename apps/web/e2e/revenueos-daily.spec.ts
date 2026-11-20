import { expect, test, type Page } from "@playwright/test";

const interactionId = "interaction-daily";

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
