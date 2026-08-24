import { expect, test, type Page } from "@playwright/test";

const opportunityId = "opportunity-daily";
const interactionId = "interaction-daily";

function dailyResponse(overrides: Record<string, unknown> = {}) {
  return {
    generatedAt: new Date().toISOString(),
    localDate: "2026-08-17",
    timezone: "Australia/Sydney",
    userDisplayName: "Alex Morgan",
    topPriority: {
      kind: "interaction",
      reasonCode: "interaction_needs_preparation",
      title: "Qantas technical review",
      context: "Economic Buyer is still unknown.",
      reason:
        "This customer interaction starts within four hours and has no completed brief.",
      ctaLabel: "Prepare for meeting",
      href: `/interactions/${interactionId}#preparation`,
      sourceId: interactionId,
      startsAt: "2026-08-17T00:00:00Z",
      dueAt: null,
    },
    nextInteraction: {
      id: interactionId,
      title: "Qantas technical review",
      companyId: "company-daily",
      companyName: "Qantas",
      opportunityId,
      opportunityName: "Network modernisation",
      interactionType: "workshop",
      lifecycleStatus: "planned",
      startsAt: "2026-08-17T00:00:00Z",
      preparationState: "not_prepared",
      context: "Economic Buyer is still unknown.",
      ctaLabel: "Prepare for meeting",
      href: `/interactions/${interactionId}#preparation`,
    },
    todayInteractions: [
      {
        id: interactionId,
        title: "Qantas technical review",
        companyId: "company-daily",
        companyName: "Qantas",
        opportunityId,
        opportunityName: "Network modernisation",
        interactionType: "workshop",
        lifecycleStatus: "planned",
        startsAt: "2026-08-17T00:00:00Z",
        preparationState: "not_prepared",
        context: "Economic Buyer is still unknown.",
        ctaLabel: "Prepare for meeting",
        href: `/interactions/${interactionId}#preparation`,
      },
      {
        id: "interaction-later",
        title: "Commercial follow-up",
        companyId: "company-daily",
        companyName: "Qantas",
        opportunityId,
        opportunityName: "Network modernisation",
        interactionType: "phone_call",
        lifecycleStatus: "planned",
        startsAt: "2026-08-17T05:00:00Z",
        preparationState: "prepared",
        context: "Network modernisation",
        ctaLabel: "Prepare",
        href: "/interactions/interaction-later#preparation",
      },
    ],
    totalTodayInteractions: 2,
    actions: {
      attentionCount: 2,
      overdueCount: 1,
      dueTodayCount: 1,
      pendingReviewCount: 1,
      approvedOpenCount: 1,
      truncated: false,
      items: [
        {
          id: "action-daily",
          title: "Send security documentation",
          opportunityId,
          opportunityName: "Network modernisation",
          companyName: "Qantas",
          priority: "high",
          reviewStatus: "proposed",
          timing: "overdue",
          dueAt: "2026-08-16T01:00:00Z",
          state: "needs_review",
          stateLabel: "Needs review",
          ctaLabel: "Review",
          href: `/opportunities/${opportunityId}#recommended-actions`,
        },
        {
          id: "action-approved",
          title: "Confirm the pilot scope",
          opportunityId,
          opportunityName: "Network modernisation",
          companyName: "Qantas",
          priority: "normal",
          reviewStatus: "approved",
          timing: "due_today",
          dueAt: "2026-08-17T06:00:00Z",
          state: "approved_not_complete",
          stateLabel: "Approved — not complete",
          ctaLabel: "Complete",
          href: `/opportunities/${opportunityId}#recommended-actions`,
        },
      ],
    },
    dealAttention: {
      attentionCount: 1,
      truncated: false,
      items: [
        {
          opportunityId,
          opportunityName: "Network modernisation",
          companyName: "Qantas",
          estimatedValue: "420000.00",
          currency: "AUD",
          expectedCloseDate: "2026-08-25",
          priority: "urgent",
          reasons: [
            {
              code: "upcoming_close_with_blocker",
              text: "The expected close date is approaching with an unresolved gap.",
            },
            {
              code: "methodology_gap",
              text: "Economic Buyer is still unknown.",
            },
          ],
          href: `/opportunities/${opportunityId}`,
        },
      ],
    },
    pipeline: {
      state: "single_currency",
      openOpportunityCount: 1,
      unvaluedOpportunityCount: 0,
      currencyCount: 1,
      currencies: [
        {
          currency: "AUD",
          openValue: "420000.00",
          closingThisMonthValue: "420000.00",
          openOpportunityCount: 1,
          closingThisMonthCount: 1,
        },
      ],
      safeMessage: "Open pipeline and opportunities closing this month.",
    },
    recommendations: [
      {
        sourceId: "recommendation-daily",
        opportunityId,
        opportunityName: "Network modernisation",
        recommendation: "Confirm access to the economic buyer.",
        priority: "high",
        reason: "Existing Next Best Action from final validated intelligence.",
        ctaLabel: "Review",
        href: `/opportunities/${opportunityId}#latest-next-best-action`,
      },
    ],
    availability: {
      interactions: true,
      actions: true,
      dealAttention: true,
      pipeline: true,
      recommendations: true,
      methodology: true,
      revenueBrain: true,
      targets: false,
      forecast: false,
    },
    hasOpportunities: true,
    caughtUp: false,
    ...overrides,
  };
}

async function routeDaily(page: Page, response = dailyResponse()) {
  let requests = 0;
  await page.route("http://localhost:8000/api/v1/daily**", async (route) => {
    requests += 1;
    await route.fulfill({ json: response });
  });
  return () => requests;
}

test("RevenueOS Daily keeps the complete review journey one click away", async ({
  page,
}) => {
  const requestCount = await routeDaily(page);

  await page.goto("/dashboard");

  await expect(
    page.getByRole("heading", { name: /Good .*Alex/i }),
  ).toBeVisible();
  await expect(page.getByText("Top priority")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Today’s interactions" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Actions", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Approved — not complete")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Deals needing attention" }),
  ).toBeVisible();
  const dealsSection = page
    .getByRole("heading", { name: "Deals needing attention" })
    .locator("xpath=ancestor::section[1]");
  await expect(
    dealsSection.getByText("Economic Buyer is still unknown."),
  ).toBeVisible();
  await expect(page.getByText("AUD 420,000.00").first()).toBeVisible();
  await expect(
    page.getByText("Confirm access to the economic buyer."),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Daily" })).toHaveCount(0);
  await expect(page.getByText(/deal health/i)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /forecast/i })).toHaveCount(0);
  await expect(page.getByText(/synthetic demo transcript/i)).toHaveCount(0);
  expect(requestCount()).toBe(1);

  if (process.env.CAPTURE_WO_025A_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025a-home-desktop.png",
      fullPage: true,
    });
  }

  await page.getByRole("link", { name: "Prepare for meeting" }).last().click();
  await expect(page).toHaveURL(new RegExp(`/interactions/${interactionId}`));
  await page.goto("/dashboard");

  const actions = page
    .getByRole("heading", { name: "Actions", exact: true })
    .locator("xpath=ancestor::section[1]");
  await actions.getByRole("link", { name: "Review", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/opportunities/${opportunityId}`));
  await page.goto("/dashboard");

  const deals = page
    .getByRole("heading", { name: "Deals needing attention" })
    .locator("xpath=ancestor::section[1]");
  await deals.getByRole("link", { name: "Review opportunity" }).click();
  await expect(page).toHaveURL(new RegExp(`/opportunities/${opportunityId}`));

  if (process.env.CAPTURE_WO_025_SCREENSHOT === "1") {
    await page.goto("/dashboard");
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025-revenueos-daily-desktop.png",
      fullPage: true,
    });
  }
});

test("RevenueOS Daily teaches a useful first step to a new user", async ({
  page,
}) => {
  const base = dailyResponse();
  await routeDaily(
    page,
    dailyResponse({
      topPriority: null,
      nextInteraction: null,
      todayInteractions: [],
      totalTodayInteractions: 0,
      actions: { ...base.actions, attentionCount: 0, items: [] },
      dealAttention: { attentionCount: 0, items: [], truncated: false },
      recommendations: [],
      pipeline: {
        state: "empty",
        openOpportunityCount: 0,
        unvaluedOpportunityCount: 0,
        currencyCount: 0,
        currencies: [],
        safeMessage:
          "Open pipeline will appear here when you add an opportunity.",
      },
      hasOpportunities: false,
      caughtUp: true,
    }),
  );

  await page.goto("/dashboard");

  await expect(
    page.getByRole("heading", {
      name: "Let’s get your first deal into RevenueOS.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Add an opportunity" }),
  ).toHaveAttribute("href", "/opportunities/new");
  await expect(
    page.getByRole("heading", { name: "Open pipeline" }),
  ).toHaveCount(0);
});

test("RevenueOS Daily puts the next interaction first on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await routeDaily(page);

  await page.goto("/dashboard");

  const nextLabel = page.getByText("Next", { exact: true });
  const actionsHeading = page.getByRole("heading", {
    name: "Actions",
    exact: true,
  });
  await expect(nextLabel).toBeVisible();
  await expect(actionsHeading).toBeVisible();
  const nextBox = await nextLabel.boundingBox();
  const actionsBox = await actionsHeading.boundingBox();
  expect(nextBox).not.toBeNull();
  expect(actionsBox).not.toBeNull();
  expect(nextBox?.y ?? Number.POSITIVE_INFINITY).toBeLessThan(
    actionsBox?.y ?? Number.NEGATIVE_INFINITY,
  );
  const prepareBox = await page
    .getByRole("link", { name: "Prepare for meeting" })
    .boundingBox();
  expect(prepareBox?.height ?? 0).toBeGreaterThanOrEqual(44);
  await expect(page.getByText("2 currencies", { exact: true })).toHaveCount(0);
  const mobileNavigation = page.getByRole("navigation", {
    name: "Mobile navigation",
  });
  await expect(mobileNavigation.getByRole("link")).toHaveCount(4);
  for (const label of ["Today", "Interactions", "Actions", "Search"]) {
    await expect(
      mobileNavigation.getByRole("link", { name: label, exact: true }),
    ).toBeVisible();
  }
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
    ),
  ).toBe(false);

  if (process.env.CAPTURE_WO_025A_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025a-home-mobile.png",
      fullPage: true,
    });
  }

  if (process.env.CAPTURE_WO_025_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025-revenueos-daily-mobile.png",
      fullPage: true,
    });
  }
});

test("mobile Search finds bounded Core records without an AI answer", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await routeDaily(page);
  for (const entity of ["companies", "opportunities", "interactions"]) {
    await page.route(
      `http://localhost:8000/api/v1/${entity}**`,
      async (route) => {
        const item =
          entity === "companies"
            ? { id: "company-search", name: "Qantas", industry: "Aviation" }
            : entity === "opportunities"
              ? {
                  id: "opportunity-search",
                  name: "Network modernisation",
                  companyName: "Qantas",
                  stage: "proposal",
                }
              : {
                  id: "interaction-search",
                  title: "Qantas technical review",
                  interactionType: "workshop",
                  lifecycleStatus: "planned",
                };
        await route.fulfill({
          json: {
            items: [item],
            page: 1,
            pageSize: 6,
            total: 1,
            pages: 1,
          },
        });
      },
    );
  }

  await page.goto("/dashboard");
  await page
    .getByRole("navigation", { name: "Mobile navigation" })
    .getByRole("link", { name: "Search" })
    .click();
  await page
    .getByRole("searchbox", { name: "Search your workspace" })
    .fill("Qantas");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(
    page.getByRole("link", { name: /Network modernisation/i }),
  ).toBeVisible();
  await expect(page.getByText(/does not generate an AI answer/i)).toBeVisible();
});
