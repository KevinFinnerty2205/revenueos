import { expect, test, type Page } from "@playwright/test";

const pipelineId = "11111111-1111-4111-8111-111111111111";
const scope = {
  startDate: "2026-07-01",
  endDate: "2026-08-30",
  timezone: "Australia/Sydney",
  pipelineId: null,
  ownerUserId: null,
  generatedAt: "2026-08-30T03:00:00Z",
};
const followOn = {
  cohortCount: 4,
  eligibleMatureCount: 3,
  followedByOutcomeCount: 2,
  rate: "66.7",
  immatureCount: 1,
  excludedUnassociatedCount: 0,
  excludedUntrackedCount: 0,
  windowDays: 30,
};

const metadata = {
  currentUserId: "user-1",
  pipelines: [
    {
      id: pipelineId,
      name: "RevenueOS Sales Pipeline",
      isDefault: true,
      active: true,
      stages: [
        {
          id: "stage-discovery",
          name: "Discovery",
          position: 0,
          stageType: "open",
          active: true,
        },
        {
          id: "stage-evaluation",
          name: "Evaluation",
          position: 1,
          stageType: "open",
          active: true,
        },
        {
          id: "stage-proposal",
          name: "Proposal",
          position: 2,
          stageType: "open",
          active: true,
        },
        {
          id: "stage-won",
          name: "Closed Won",
          position: 3,
          stageType: "won",
          active: true,
        },
      ],
    },
  ],
  owners: [
    { userId: "user-1", displayName: "Alex Morgan", active: true },
    { userId: "user-empty", displayName: "Taylor Empty", active: true },
  ],
  metrics: [],
  outcomeWindowDays: 30,
  maximumRangeDays: 1827,
  generatedAt: scope.generatedAt,
};

const overview = {
  scope,
  openOpportunityCount: 8,
  opportunitiesCreatedCount: 19,
  wonCount: 7,
  lostCount: 5,
  closedCount: 12,
  winRate: "58.3",
  medianSalesCycleDays: "25.0",
  wonValues: [
    { currency: "AUD", amount: "712500.00", opportunityCount: 4 },
    { currency: "USD", amount: "330000.00", opportunityCount: 3 },
  ],
  unvaluedWonCount: 0,
  hasOpportunities: true,
};

const emptyOverview = {
  ...overview,
  openOpportunityCount: 0,
  opportunitiesCreatedCount: 0,
  wonCount: 0,
  lostCount: 0,
  closedCount: 0,
  winRate: null,
  medianSalesCycleDays: null,
  wonValues: [],
  hasOpportunities: false,
};

const funnel = {
  scope: { ...scope, pipelineId },
  pipelineId,
  pipelineName: "RevenueOS Sales Pipeline",
  cohortDefinition:
    "Opportunities first entering this pipeline during the selected period; progression measured through today.",
  cohortCount: 19,
  currentOpenCount: 7,
  currentWonCount: 7,
  currentLostCount: 5,
  stages: [
    {
      stageId: "stage-discovery",
      stageName: "Discovery",
      position: 0,
      enteredCount: 18,
      advancedCount: 16,
      stillOpenCount: 2,
      closedLostCount: 0,
      otherNotAdvancedCount: 0,
      advanceRate: "88.9",
    },
    {
      stageId: "stage-evaluation",
      stageName: "Evaluation",
      position: 1,
      enteredCount: 16,
      advancedCount: 13,
      stillOpenCount: 2,
      closedLostCount: 1,
      otherNotAdvancedCount: 0,
      advanceRate: "81.3",
    },
    {
      stageId: "stage-proposal",
      stageName: "Proposal",
      position: 2,
      enteredCount: 12,
      advancedCount: 9,
      stillOpenCount: 1,
      closedLostCount: 2,
      otherNotAdvancedCount: 0,
      advanceRate: "75.0",
    },
  ],
  stageDurations: [
    {
      stageId: "stage-discovery",
      stageName: "Discovery",
      medianCompletedDays: "5.0",
      completedIntervalCount: 16,
    },
    {
      stageId: "stage-evaluation",
      stageName: "Evaluation",
      medianCompletedDays: "5.0",
      completedIntervalCount: 13,
    },
    {
      stageId: "stage-proposal",
      stageName: "Proposal",
      medianCompletedDays: "5.0",
      completedIntervalCount: 9,
    },
  ],
  coverage: {
    reliableOpportunityCount: 19,
    baselineOnlyOpportunityCount: 1,
    earliestReliableEventAt: "2026-07-01T01:00:00Z",
    disclosure:
      "Stage conversion excludes 1 baseline-only Opportunity in this period. Earlier history was not reconstructed.",
  },
};

const activity = {
  scope,
  phoneCallsCompletedCount: 4,
  meetingsCompletedCount: 4,
  callsFollowedByMeeting: followOn,
  meetingsFollowedByProgression: {
    ...followOn,
    followedByOutcomeCount: 2,
    rate: "66.7",
  },
  outreachAvailable: false,
  liveOutreachSentCount: 0,
  outreachFollowedByMeeting: null,
  associationDisclosure:
    "These are recorded activities followed by a later recorded outcome within 30 days. They are associations, not attribution or proof of causation.",
};

const winLoss = {
  scope,
  wonCount: 7,
  lostCount: 5,
  winRate: "58.3",
  wonReasons: [
    {
      reason: "solution_fit",
      label: "Solution fit",
      count: 2,
      percentage: "28.6",
    },
    { reason: "commercial", label: "Commercial", count: 2, percentage: "28.6" },
    {
      reason: "relationship",
      label: "Relationship",
      count: 2,
      percentage: "28.6",
    },
    {
      reason: "implementation",
      label: "Implementation",
      count: 1,
      percentage: "14.3",
    },
  ],
  lostReasons: [
    { reason: "budget", label: "Budget", count: 1, percentage: "20.0" },
    { reason: "competitor", label: "Competitor", count: 1, percentage: "20.0" },
    { reason: "timing", label: "Timing", count: 1, percentage: "20.0" },
    {
      reason: "requirements_fit",
      label: "Requirements fit",
      count: 1,
      percentage: "20.0",
    },
    {
      reason: "procurement",
      label: "Procurement",
      count: 1,
      percentage: "20.0",
    },
  ],
  lossStages: [{ stageId: "stage-proposal", stageName: "Proposal", count: 5 }],
  salesCycles: [
    { outcome: "won", medianDays: "25.0", sampleSize: 7 },
    { outcome: "lost", medianDays: "15.0", sampleSize: 5 },
  ],
  values: [
    {
      outcome: "won",
      currency: "AUD",
      amount: "712500.00",
      medianAmount: "175000.00",
      opportunityCount: 4,
    },
    {
      outcome: "won",
      currency: "USD",
      amount: "330000.00",
      medianAmount: "105000.00",
      opportunityCount: 3,
    },
    {
      outcome: "lost",
      currency: "AUD",
      amount: "530000.00",
      medianAmount: "142500.00",
      opportunityCount: 4,
    },
  ],
  unvaluedWonCount: 0,
  unvaluedLostCount: 1,
  reasonProvenance: "seller_reported",
  notesAggregated: false,
};

async function routeInsights(page: Page) {
  await page.route("http://localhost:8000/api/v1/me", async (route) => {
    await route.fulfill({
      json: {
        user: {
          id: "user-1",
          externalAuthId: "user_dev_001",
          displayName: "Alex Morgan",
          email: "alex@example.test",
        },
        organisation: {
          id: "organisation-1",
          name: "Synthetic Revenue Team",
          slug: "synthetic-revenue-team",
        },
        role: "admin",
        authMode: "mock",
        requestId: "request-sales-insights-e2e",
      },
    });
  });
  await page.route(
    "http://localhost:8000/api/v1/insights/sales/**",
    async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith("/metadata"))
        return route.fulfill({ json: metadata });
      if (url.pathname.endsWith("/overview")) {
        return route.fulfill({
          json:
            url.searchParams.get("ownerUserId") === "user-empty"
              ? emptyOverview
              : overview,
        });
      }
      if (url.pathname.endsWith("/funnel"))
        return route.fulfill({ json: funnel });
      if (url.pathname.endsWith("/activity"))
        return route.fulfill({ json: activity });
      return route.fulfill({ json: winLoss });
    },
  );
  await page.route("http://localhost:8000/api/v1/beta/capabilities", (route) =>
    route.fulfill({ json: { featureFlags: { salesAnalytics: true } } }),
  );
  for (const path of [
    "prospect/availability",
    "engage/availability",
    "create/availability",
  ]) {
    await page.route(`http://localhost:8000/api/v1/${path}`, (route) =>
      route.fulfill({ json: { enabled: false } }),
    );
  }
}

const assets = "../../docs/07-sprints/assets";

test("Sales Insights reconciles exact funnel, activity and Win/Loss fixtures", async ({
  page,
}) => {
  await routeInsights(page);
  await page.goto("/insights");

  await expect(
    page.getByRole("heading", { name: "Sales insights" }),
  ).toBeVisible();
  await expect(page.getByText("58.3%", { exact: true })).toBeVisible();
  await expect(page.getByText("25 days", { exact: true })).toBeVisible();
  await expect(page.getByText("AUD", { exact: true })).toBeVisible();
  await expect(page.getByText("USD", { exact: true })).toBeVisible();
  await page.screenshot({
    path: `${assets}/wo-036-insights-overview.png`,
    fullPage: true,
  });

  await page.getByRole("tab", { name: "Funnel" }).click();
  await expect(page.getByText(/choose one pipeline/i)).toBeVisible();
  await page.getByLabel("Pipeline").selectOption(pipelineId);
  await expect(
    page.getByText("RevenueOS Sales Pipeline progression"),
  ).toBeVisible();
  await expect(page.getByText(/baseline-only/i)).toBeVisible();
  await expect(
    page.getByText(/skipped stages are not inferred/i),
  ).toBeVisible();
  await page.getByText("View exact values").first().click();
  await expect(
    page.getByRole("table", { name: "Funnel exact values" }),
  ).toContainText("88.9%");
  await page.screenshot({
    path: `${assets}/wo-036-insights-funnel.png`,
    fullPage: true,
  });

  await page.getByRole("tab", { name: "Activity" }).click();
  await expect(page.getByText("Completed phone calls")).toBeVisible();
  await expect(page.getByText("Calls followed by a meeting")).toBeVisible();
  await expect(
    page.getByText(/not attribution or proof of causation/i),
  ).toBeVisible();
  await page.screenshot({
    path: `${assets}/wo-036-insights-activity.png`,
    fullPage: true,
  });

  await page.getByRole("tab", { name: "Win / loss" }).click();
  await expect(page.getByText("Why we won", { exact: true })).toBeVisible();
  await expect(
    page.getByText(/seller-reported structured fields/i),
  ).toBeVisible();
  await expect(
    page.getByText(/free-text win\/loss notes are intentionally excluded/i),
  ).toBeVisible();
  await page.screenshot({
    path: `${assets}/wo-036-insights-win-loss.png`,
    fullPage: true,
  });

  await page.getByRole("tab", { name: "Overview" }).click();
  await page.getByLabel("Owner").selectOption("user-empty");
  await expect(
    page.getByText(/no opportunities matched this period/i),
  ).toBeVisible();
  await page.screenshot({
    path: `${assets}/wo-036-insights-empty.png`,
    fullPage: true,
  });
});

test("Sales Insights remains usable at a 390-pixel viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await routeInsights(page);
  await page.goto("/insights");
  await expect(page.getByText("Open opportunities")).toBeVisible();
  await page.screenshot({
    path: `${assets}/wo-036-insights-mobile-overview.png`,
    fullPage: true,
  });

  await page.getByLabel("Pipeline").selectOption(pipelineId);
  for (const [tabName, fileName, expectedText] of [
    ["Funnel", "funnel", "RevenueOS Sales Pipeline progression"],
    ["Activity", "activity", "Calls followed by a meeting"],
    ["Win / loss", "win-loss", "Why we won"],
  ] as const) {
    await page.getByRole("tab", { name: tabName }).click();
    await expect(page.getByText(expectedText, { exact: true })).toBeVisible();
    await page.screenshot({
      path: `${assets}/wo-036-insights-mobile-${fileName}.png`,
      fullPage: true,
    });
  }
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
