import { expect, test, type Page } from "@playwright/test";

const opportunityId = "opportunity-pipeline";

const stages = [
  {
    id: "stage-discovery",
    pipelineId: "pipeline-1",
    key: "discovery",
    name: "Discovery",
    position: 0,
    stageType: "open",
    guidance: "Confirm the problem and buying context.",
    active: true,
    archivedAt: null,
    currentOpportunityCount: 1,
  },
  {
    id: "stage-proposal",
    pipelineId: "pipeline-1",
    key: "proposal",
    name: "Proposal",
    position: 1,
    stageType: "open",
    guidance: "Review the commercial proposal with the buying team.",
    active: true,
    archivedAt: null,
    currentOpportunityCount: 0,
  },
  {
    id: "stage-won",
    pipelineId: "pipeline-1",
    key: "closed_won",
    name: "Closed Won",
    position: 2,
    stageType: "won",
    guidance: null,
    active: true,
    archivedAt: null,
    currentOpportunityCount: 0,
  },
  {
    id: "stage-lost",
    pipelineId: "pipeline-1",
    key: "closed_lost",
    name: "Closed Lost",
    position: 3,
    stageType: "lost",
    guidance: null,
    active: true,
    archivedAt: null,
    currentOpportunityCount: 0,
  },
];

const pipeline = {
  id: "pipeline-1",
  name: "RevenueOS Sales Pipeline",
  isDefault: true,
  active: true,
  archivedAt: null,
  stages,
  createdAt: "2026-08-30T00:00:00Z",
  updatedAt: "2026-08-30T00:00:00Z",
};

async function routeShell(page: Page) {
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
        requestId: "request-native-pipeline-e2e",
      },
    });
  });
  await page.route(
    "http://localhost:8000/api/v1/beta/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          featureFlags: { opportunityWorkspace: false, nativePipeline: true },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
}

async function routePipeline(page: Page, externallyManaged = false) {
  let currentStage = stages[0];
  let status: "open" | "lost" = "open";
  let actualCloseDate: string | null = null;
  let outcomeReason: string | null = null;
  const history: Array<Record<string, unknown>> = [
    {
      id: "event-baseline",
      fromPipelineId: null,
      toPipelineId: pipeline.id,
      fromStageId: null,
      toStageId: stages[0].id,
      fromStageName: null,
      toStageName: stages[0].name,
      fromStageType: null,
      toStageType: "open",
      changedByUserId: null,
      changedByName: null,
      changedAt: "2026-08-28T00:00:00Z",
      source: "migration_baseline",
      isBaseline: true,
      previousStageEnteredAt: null,
      outcomeReason: null,
      outcomeNote: null,
      outcomeProvenance: null,
    },
  ];

  const authority = externallyManaged
    ? {
        stageChangesAllowed: false,
        managedExternally: true,
        authorityMessage:
          "Stages are managed in HubSpot. Use the reviewed CRM update flow.",
      }
    : {
        stageChangesAllowed: true,
        managedExternally: false,
        authorityMessage: null,
      };

  const card = (overrides: Record<string, unknown> = {}) => ({
    opportunityId,
    opportunityName: "Platform expansion",
    companyId: "company-1",
    companyName: "Acme Australia",
    pipelineId: pipeline.id,
    pipelineName: pipeline.name,
    stageId: currentStage.id,
    stageName: currentStage.name,
    stageType: currentStage.stageType,
    status,
    estimatedValue: "125000.50",
    currency: "AUD",
    expectedCloseDate: "2026-08-31",
    actualCloseDate,
    ownerUserId: "user-1",
    ownerName: "Alex Morgan",
    stageEnteredAt: "2026-08-28T00:00:00Z",
    stageTrackingStartedAt: "2026-08-28T00:00:00Z",
    daysInStage: 2,
    nextAction: "Confirm the procurement owner.",
    attentionReasons: ["Overdue high-priority Action"],
    outcomeReason,
    outcomeProvenance: outcomeReason ? "seller_reported" : null,
    ...overrides,
  });

  await page.route("http://localhost:8000/api/v1/pipeline**", async (route) => {
    const view =
      new URL(route.request().url()).searchParams.get("view") ?? "open";
    const cards =
      view === "closed"
        ? [
            card({
              opportunityId: "opportunity-closed",
              opportunityName: "Renewal programme",
              stageId: stages[3].id,
              stageName: stages[3].name,
              stageType: "lost",
              status: "lost",
              actualCloseDate: "2026-08-25",
              outcomeReason: "timing",
              outcomeProvenance: "seller_reported",
              attentionReasons: [],
            }),
          ]
        : status === "open"
          ? [
              card(),
              card({
                opportunityId: "opportunity-usd",
                opportunityName: "US services pilot",
                companyId: "company-2",
                companyName: "Northwind",
                stageId: stages[1].id,
                stageName: stages[1].name,
                estimatedValue: "50000.00",
                currency: "USD",
                ownerUserId: "user-2",
                ownerName: "Jordan Lee",
                nextAction: null,
                attentionReasons: [],
              }),
            ]
          : [];
    await route.fulfill({
      json: {
        pipeline,
        pipelines: [pipeline],
        view,
        summary: {
          openOpportunityCount: cards.length,
          needsAttentionCount: cards.filter(
            (item) => item.attentionReasons.length,
          ).length,
          closeDatesThisMonthCount: cards.length,
          unvaluedOpportunityCount: 0,
          values:
            view === "open"
              ? [
                  { currency: "AUD", amount: "125000.50", opportunityCount: 1 },
                  { currency: "USD", amount: "50000.00", opportunityCount: 1 },
                ]
              : [{ currency: "AUD", amount: "125000.50", opportunityCount: 1 }],
        },
        cards,
        ...authority,
        generatedAt: "2026-08-30T01:00:00Z",
      },
    });
  });

  await page.route(
    `http://localhost:8000/api/v1/crm/records/opportunity/${opportunityId}`,
    async (route) => {
      await route.fulfill({
        json: {
          entityType: "opportunity",
          entityId: opportunityId,
          title: "Platform expansion",
          ownerUserId: "user-1",
          ownerName: "Alex Morgan",
          archivedAt: null,
          recordUpdatedAt: "2026-08-30T01:00:00Z",
          mode: externallyManaged ? "external" : "native",
          crmEnabled: true,
          canManage: true,
          customFieldsReadOnly: externallyManaged,
          fieldAuthority: {},
          coreFields: [],
          customFields: [],
          history: [],
          activity: [],
        },
      });
    },
  );

  const state = () => ({
    opportunityId,
    status,
    pipeline,
    stage: currentStage,
    stageEnteredAt:
      status === "open" ? "2026-08-28T00:00:00Z" : "2026-08-30T01:00:00Z",
    stageTrackingStartedAt: "2026-08-28T00:00:00Z",
    daysInStage: status === "open" ? 2 : 0,
    actualCloseDate,
    outcomeReason,
    outcomeNote: outcomeReason
      ? "Seller reported customer timing changed."
      : null,
    outcomeProvenance: outcomeReason ? "seller_reported" : null,
    availablePipelines: [pipeline],
    history,
    ...authority,
  });

  await page.route(
    `http://localhost:8000/api/v1/opportunities/${opportunityId}/**`,
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (request.method() === "GET" && path.endsWith("/pipeline")) {
        await route.fulfill({ json: state() });
        return;
      }
      if (externallyManaged) {
        await route.fulfill({
          status: 409,
          json: {
            code: "external_stage_authority",
            message: "This stage is managed in HubSpot.",
            requestId: "request-external-authority",
          },
        });
        return;
      }
      const body = request.postDataJSON() as Record<string, string>;
      const from = currentStage;
      if (path.endsWith("/stage")) {
        currentStage =
          stages.find((stage) => stage.id === body.targetStageId) ??
          currentStage;
      } else if (path.endsWith("/close-lost")) {
        currentStage = stages[3];
        status = "lost";
        actualCloseDate = body.actualCloseDate;
        outcomeReason = body.outcomeReason;
      } else if (path.endsWith("/reopen")) {
        currentStage =
          stages.find((stage) => stage.id === body.targetStageId) ?? stages[0];
        status = "open";
        actualCloseDate = null;
        outcomeReason = null;
      }
      history.push({
        id: `event-${history.length + 1}`,
        fromPipelineId: pipeline.id,
        toPipelineId: pipeline.id,
        fromStageId: from.id,
        toStageId: currentStage.id,
        fromStageName: from.name,
        toStageName: currentStage.name,
        fromStageType: from.stageType,
        toStageType: currentStage.stageType,
        changedByUserId: "user-1",
        changedByName: "Alex Morgan",
        changedAt: "2026-08-30T01:00:00Z",
        source: "manual",
        isBaseline: false,
        previousStageEnteredAt: "2026-08-28T00:00:00Z",
        outcomeReason: path.endsWith("/close-lost") ? body.outcomeReason : null,
        outcomeNote: path.endsWith("/close-lost") ? body.outcomeNote : null,
        outcomeProvenance: path.endsWith("/close-lost")
          ? "seller_reported"
          : null,
      });
      await route.fulfill({ json: state() });
    },
  );
}

test("native board supports accessible stage movement, list and closed views without currency blending", async ({
  page,
}) => {
  await routeShell(page);
  await routePipeline(page);
  await page.goto("/opportunities");

  await expect(
    page.getByRole("heading", { name: "Pipeline", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/\$125,001.*USD.*50,000/).first()).toBeVisible();
  await expect(
    page.getByText("Overdue high-priority Action").last(),
  ).toBeVisible();
  const card = page
    .getByRole("article")
    .filter({ hasText: "Platform expansion" })
    .last();
  await card.getByLabel("Move stage").selectOption("stage-proposal");
  await expect(card.getByLabel("Move stage")).toHaveValue("stage-proposal");

  await page.getByRole("button", { name: "List" }).click();
  await expect(
    page.getByRole("columnheader", { name: "Time in stage" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Closed" }).click();
  await expect(
    page.getByRole("link", { name: "Renewal programme" }),
  ).toBeVisible();
  await expect(page.getByText("Timing · seller reported")).toBeVisible();

  await page.getByRole("button", { name: "Board" }).click();
  if (process.env.CAPTURE_WO_035_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-035-native-pipeline-board.png",
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  const hasHorizontalOverflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});

test("close Lost captures seller-reported outcome and reopen preserves readable history", async ({
  page,
}) => {
  await routeShell(page);
  await routePipeline(page);
  await page.goto(`/opportunities/${opportunityId}`);

  await expect(
    page.getByRole("heading", { name: "Discovery", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mark Lost" }).click();
  await page.getByLabel("Actual close date").fill("2026-08-30");
  await page
    .getByLabel("Why was this opportunity lost?")
    .selectOption("timing");
  await page
    .getByLabel("Internal outcome note (optional)")
    .fill("Seller reported customer timing changed.");
  await page.getByRole("button", { name: "Close Lost" }).click();
  await expect(
    page.getByText("Timing · seller reported").first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "Reopen opportunity" }).click();
  await page.getByLabel("Open stage").selectOption("stage-proposal");
  await page.getByRole("button", { name: "Reopen", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Proposal", exact: true }),
  ).toBeVisible();
  await page.getByText("Stage history", { exact: true }).click();
  await expect(
    page.getByText("Outcome: Timing · seller reported"),
  ).toBeVisible();
});

test("external CRM mode is explicitly read-only for stage authority", async ({
  page,
}) => {
  await routeShell(page);
  await routePipeline(page, true);
  await page.goto("/opportunities");

  await expect(page.getByText("Managed in HubSpot.")).toBeVisible();
  await expect(page.getByLabel("Move stage")).toHaveCount(0);
});
