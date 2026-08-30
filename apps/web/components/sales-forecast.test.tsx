import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SalesForecast } from "@/components/sales-forecast";

const currentUserId = "22222222-2222-4222-8222-222222222222";
const opportunityId = "33333333-3333-4333-8333-333333333333";
const pipelineId = "44444444-4444-4444-8444-444444444444";

const metadata = {
  currentUserId,
  currentUserRole: "admin",
  organisationTimezone: "Australia/Sydney",
  owners: [{ userId: currentUserId, displayName: "Alex Seller", active: true }],
  pipelines: [{ id: pipelineId, name: "New business", active: true }],
  canViewOrganisationForecast: true,
  canReviewManagerView: true,
  modelVersion: "forecast_historical_stage_outcome_v1",
  modelLookbackDays: 730,
  modelMinimumSample: 10,
  supportedPeriodTypes: ["month", "quarter"],
  categories: ["commit", "likely", "possible", "not_this_period"],
};

const baseline = {
  status: "available",
  modelVersion: "forecast_historical_stage_outcome_v1",
  pipelineId,
  pipelineName: "New business",
  stageId: "stage-1",
  stageName: "Negotiation",
  wonCount: 8,
  lostCount: 4,
  sampleSize: 12,
  observedWinRate: "66.7",
  expectedContribution: "120000.00",
  lookbackStart: "2024-09-01",
  lookbackEnd: "2026-08-30",
  minimumSample: 10,
  explanation:
    "8 of 12 reliably tracked Opportunities that entered this exact Pipeline stage finished Won.",
};

const period = {
  id: "55555555-5555-4555-8555-555555555555",
  periodType: "quarter",
  periodStart: "2026-07-01",
  periodEnd: "2026-09-30",
  periodLabel: "Q3 2026",
  timezone: "Australia/Sydney",
  status: "active",
};

const history = {
  opportunityId,
  opportunityName: "Northstar renewal",
  period,
  latestStaleReasons: ["amount_changed"],
  revisions: [
    {
      id: "77777777-7777-4777-8777-777777777777",
      revisionNumber: 1,
      category: "commit",
      createdByUserId: currentUserId,
      createdByDisplayName: "Alex Seller",
      ownerUserIdSnapshot: currentUserId,
      amountSnapshot: "175000.00",
      currencySnapshot: "AUD",
      expectedCloseDateSnapshot: "2026-09-15",
      pipelineIdSnapshot: pipelineId,
      pipelineNameSnapshot: "New business",
      stageIdSnapshot: "stage-1",
      stageNameSnapshot: "Negotiation",
      opportunityStatusSnapshot: "open",
      historicalBaseline: baseline,
      createdAt: "2026-08-20T03:00:00Z",
    },
  ],
};

const forecast = {
  period,
  currency: "AUD",
  pipelineId: null,
  ownerUserId: null,
  organisationScope: true,
  actual: {
    state: "available",
    amount: "54000.00",
    calculatedThrough: "2026-08-30",
    metricId: "won_value",
    metricDefinitionVersion: "1",
  },
  targets: [
    {
      id: "target-1",
      label: "Organisation won value",
      scope: "organisation",
      origin: "admin_assigned",
      targetValue: "400000.00",
    },
  ],
  sellerForecast: {
    commit: { amount: "180000.00", opportunityCount: 1, unvaluedCount: 0 },
    likely: { amount: "280000.00", opportunityCount: 2, unvaluedCount: 0 },
    possible: { amount: "360000.00", opportunityCount: 3, unvaluedCount: 0 },
    unreviewedCount: 1,
    notThisPeriodCount: 0,
    needsReviewCount: 1,
    disclosure:
      "Commit is Commit only; Likely adds Likely; Possible adds Possible. No probability is applied.",
  },
  managerForecast: {
    commit: { amount: "0.00", opportunityCount: 0, unvaluedCount: 0 },
    likely: { amount: "180000.00", opportunityCount: 1, unvaluedCount: 0 },
    possible: { amount: "180000.00", opportunityCount: 1, unvaluedCount: 0 },
    unreviewedCount: 3,
    notThisPeriodCount: 0,
    needsReviewCount: 0,
    disclosure:
      "This independent manager view is not blended with the seller forecast.",
  },
  revenueosBaseline: {
    expectedContribution: "273333.33",
    coveredOpportunityCount: 3,
    uncoveredOpportunityCount: 1,
    coveredAmount: "410000.00",
    uncoveredAmount: "50000.00",
    unvaluedOpportunityCount: 0,
    modelVersion: "forecast_historical_stage_outcome_v1",
    lookbackDays: 730,
    minimumSample: 10,
    disclosure:
      "This separate historical baseline is not a seller forecast and is not a range.",
  },
  inputQuality: {
    eligibleOpportunityCount: 4,
    valuedOpportunityCount: 4,
    unvaluedOpportunityCount: 0,
    missingExpectedCloseCount: 1,
    insufficientHistoryCount: 1,
  },
  opportunities: [
    {
      opportunityId,
      opportunityName: "Northstar renewal",
      companyName: "Northstar",
      ownerUserId: currentUserId,
      ownerDisplayName: "Alex Seller",
      amount: "180000.00",
      currency: "AUD",
      expectedCloseDate: "2026-09-15",
      pipelineId,
      pipelineName: "New business",
      stageId: "stage-1",
      stageName: "Negotiation",
      stageEnteredAt: "2026-08-01T00:00:00Z",
      status: "open",
      judgment: {
        judgmentId: "judgment-1",
        revisionId: "revision-1",
        revisionNumber: 1,
        category: "commit",
        createdByUserId: currentUserId,
        createdByDisplayName: "Alex Seller",
        createdAt: "2026-08-20T03:00:00Z",
        staleReasons: ["amount_changed"],
        canReview: true,
      },
      managerJudgment: {
        judgmentId: "manager-judgment-1",
        revisionId: "manager-revision-1",
        revisionNumber: 1,
        category: "likely",
        createdByUserId: currentUserId,
        createdByDisplayName: "Alex Manager",
        createdAt: "2026-08-21T03:00:00Z",
        staleReasons: [],
        canReview: true,
      },
      historicalBaseline: baseline,
    },
  ],
  totalOpportunities: 1,
  page: 1,
  pageSize: 100,
  generatedAt: "2026-08-30T03:00:00Z",
};

const calibration = {
  periodType: "quarter",
  periodsIncluded: 2,
  categories: [
    {
      category: "commit",
      assessedCount: 8,
      realisedWonCount: 6,
      realisationRate: "75.0",
    },
    {
      category: "likely",
      assessedCount: 3,
      realisedWonCount: 1,
      realisationRate: null,
    },
    {
      category: "possible",
      assessedCount: 0,
      realisedWonCount: 0,
      realisationRate: null,
    },
  ],
  minimumRateSample: 5,
  disclosure:
    "Final realization is not a rep score or lead-time accuracy measure.",
  generatedAt: "2026-08-30T03:00:00Z",
};

function json(payload: object, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("sales forecast", () => {
  it("keeps actual, target, seller range and historical baseline separate", async () => {
    const requests: RequestInit[] = [];
    const requestUrls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/forecast/metadata")) return json(metadata);
        if (url.includes("/calibration")) return json(calibration);
        if (url.includes("/history")) return json(history);
        if (init?.method === "POST") {
          requests.push(init);
          requestUrls.push(url);
          return json(history);
        }
        return json(forecast);
      }),
    );

    render(<SalesForecast />);

    expect(await screen.findByText("Actual won")).toBeVisible();
    expect(screen.getByText("$54,000")).toBeVisible();
    expect(screen.getByText("$400,000")).toBeVisible();
    expect(screen.getAllByText("$180,000").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$273,333").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/not a seller forecast and is not a range/i),
    ).toBeVisible();
    expect(screen.getByText(/no probability is applied/i)).toBeVisible();
    expect(
      screen.getByText("Independent manager forecast range"),
    ).toBeVisible();
    expect(
      screen.getByText(/not blended with the seller forecast/i),
    ).toBeVisible();
    expect(screen.getByText(/missing expected close date/i)).toBeVisible();
    expect(screen.getByText("Needs review")).toBeVisible();

    fireEvent.click(
      screen.getByRole("button", { name: "View review history" }),
    );
    expect(await screen.findByText(/Revision 1: Commit/i)).toBeVisible();

    fireEvent.change(screen.getByLabelText("Seller category"), {
      target: { value: "likely" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save new revision" }));
    await waitFor(() => expect(requests).toHaveLength(1));
    expect(JSON.parse(String(requests[0]?.body))).toMatchObject({
      category: "likely",
      expectedRevisionNumber: 1,
      periodType: "quarter",
    });

    fireEvent.change(screen.getByLabelText("Manager category"), {
      target: { value: "possible" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save manager revision" }),
    );
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(JSON.parse(String(requests[1]?.body))).toMatchObject({
      category: "possible",
      expectedRevisionNumber: 1,
    });
    expect(requestUrls[1]).toContain("manager-judgments");
  });

  it("shows a safe empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url.endsWith("/api/v1/forecast/metadata")) return json(metadata);
        if (url.includes("/calibration")) return json(calibration);
        return json({ ...forecast, opportunities: [], totalOpportunities: 0 });
      }),
    );
    render(<SalesForecast />);
    expect(
      await screen.findByText(/No open opportunities close in this period/i),
    ).toBeVisible();
  });

  it("requires an explicit category for an unreviewed opportunity", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url.endsWith("/api/v1/forecast/metadata")) return json(metadata);
        if (url.includes("/calibration")) return json(calibration);
        return json({
          ...forecast,
          opportunities: [
            {
              ...forecast.opportunities[0],
              judgment: null,
            },
          ],
        });
      }),
    );

    render(<SalesForecast />);

    expect(
      await screen.findByRole("option", { name: "Choose a category" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Save judgment" }),
    ).toBeDisabled();
  });
});
