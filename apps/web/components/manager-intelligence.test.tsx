import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ManagerDealReviewPanel } from "@/components/manager-deal-review";
import { ManagerHomeAttention } from "@/components/manager-home-attention";
import { ManagerInsightsOverview } from "@/components/manager-insights-overview";

const source = {
  sourceType: "opportunity",
  sourceId: "opportunity-1",
  label: "Current Opportunity state",
  href: "/opportunities/opportunity-1",
};
const reason = {
  id: "close_date_passed:opportunity-1",
  code: "close_date_passed",
  label: "Close date passed",
  explanation:
    "The canonical expected close date is in the past while the Opportunity remains open.",
  detectedAt: "2026-08-30T00:00:00Z",
  sources: [source],
};
const deal = {
  opportunityId: "opportunity-1",
  opportunityName: "Northstar renewal",
  companyName: "Northstar",
  ownerUserId: "user-1",
  ownerDisplayName: "Alex Seller",
  pipelineId: "pipeline-1",
  pipelineName: "New business",
  stageId: "stage-1",
  stageName: "Negotiation",
  amount: "180000.00",
  currency: "AUD",
  expectedCloseDate: "2026-09-15",
  sellerForecast: {
    category: "commit",
    revisionNumber: 1,
    reviewedAt: "2026-08-20T00:00:00Z",
    staleReasons: [],
  },
  managerForecast: {
    category: "likely",
    revisionNumber: 1,
    reviewedAt: "2026-08-21T00:00:00Z",
    staleReasons: [],
  },
  reasons: [reason],
  href: "/opportunities/opportunity-1",
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

describe("manager intelligence", () => {
  it("keeps Home compact and deal-centric", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        json({
          total: 1,
          summaries: [],
          items: [deal],
          page: 1,
          pageSize: 5,
          generatedAt: "2026-08-30T00:00:00Z",
        }),
      ),
    );
    render(<ManagerHomeAttention />);
    expect(
      await screen.findByRole("heading", { name: "Deals needing attention" }),
    ).toBeVisible();
    expect(screen.getByText("Northstar renewal")).toBeVisible();
    expect(screen.getByText(/close date passed/i)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open manager view" }),
    ).toHaveAttribute("href", "/opportunities?view=attention");
  });

  it("shows separate forecast references and organisation targets in Insights", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        json({
          periodLabel: "Q3 2026",
          currency: "AUD",
          actual: {
            state: "available",
            amount: "54000.00",
            calculatedThrough: "2026-08-30",
            metricId: "won_value",
            metricDefinitionVersion: "1",
          },
          organisationTargets: [
            {
              id: "target-1",
              label: "Organisation target",
              scope: "organisation",
              origin: "admin_assigned",
              targetValue: "400000.00",
            },
          ],
          sellerForecast: {
            commit: {
              amount: "180000.00",
              opportunityCount: 1,
              unvaluedCount: 0,
            },
            likely: {
              amount: "280000.00",
              opportunityCount: 2,
              unvaluedCount: 0,
            },
            possible: {
              amount: "360000.00",
              opportunityCount: 3,
              unvaluedCount: 0,
            },
            unreviewedCount: 0,
            notThisPeriodCount: 0,
            needsReviewCount: 0,
            disclosure: "Seller view",
          },
          managerForecast: {
            commit: { amount: "0.00", opportunityCount: 0, unvaluedCount: 0 },
            likely: {
              amount: "180000.00",
              opportunityCount: 1,
              unvaluedCount: 0,
            },
            possible: {
              amount: "180000.00",
              opportunityCount: 1,
              unvaluedCount: 0,
            },
            unreviewedCount: 2,
            notThisPeriodCount: 0,
            needsReviewCount: 0,
            disclosure: "Manager view",
          },
          revenueosBaseline: {
            expectedContribution: "120000.00",
            coveredOpportunityCount: 1,
            uncoveredOpportunityCount: 0,
            coveredAmount: "180000.00",
            uncoveredAmount: "0.00",
            unvaluedOpportunityCount: 0,
            modelVersion: "v1",
            lookbackDays: 730,
            minimumSample: 10,
            disclosure: "Baseline",
          },
          dealsNeedingAttention: 1,
          topAttentionReasons: [],
          generatedAt: "2026-08-30T00:00:00Z",
        }),
      ),
    );
    render(<ManagerInsightsOverview />);
    expect(
      await screen.findByText("Organisation sales overview"),
    ).toBeVisible();
    expect(screen.getByText("Actual won")).toBeVisible();
    expect(screen.getByText("Organisation target")).toBeVisible();
    expect(screen.getByText("Seller Likely")).toBeVisible();
    expect(screen.getByText("Manager Likely")).toBeVisible();
    expect(screen.getByText("RevenueOS baseline")).toBeVisible();
    expect(screen.getByText(/no blended final forecast/i)).toBeVisible();
  });

  it("provides source-backed questions and saves only a manager forecast revision", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    const detail = {
      deal,
      historicalBaseline: {
        state: "available",
        expectedContribution: "120000.00",
        wonCount: 8,
        lostCount: 4,
        explanation: "8 of 12 comparable Opportunities finished Won.",
      },
      methodologyGaps: [],
      currentActions: [
        {
          id: "task-1",
          title: "Confirm procurement owner",
          status: "open",
          priority: "high",
          dueAt: "2026-08-31T00:00:00Z",
          href: "/opportunities/opportunity-1#actions",
        },
      ],
      latestInteraction: null,
      recentChanges: [
        {
          id: "stage:event-1",
          changeType: "stage_changed",
          label: "Stage changed to Negotiation",
          changedAt: "2026-08-29T00:00:00Z",
          source: {
            sourceType: "pipeline_stage_event",
            sourceId: "event-1",
            label: "Pipeline stage history",
            href: null,
          },
        },
      ],
      questions: [
        {
          id: "question:close",
          question:
            "What is the current expected close date, and what customer evidence supports it?",
          whyShown: reason.explanation,
          sourceReasonIds: [reason.id],
          sources: [source],
        },
      ],
      generatedAt: "2026-08-30T00:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        requests.push({ url: String(input), init });
        return json(init?.method === "POST" ? { revisions: [] } : detail);
      }),
    );
    render(<ManagerDealReviewPanel opportunityId="opportunity-1" />);

    expect(await screen.findByText("What matters for this deal")).toBeVisible();
    expect(screen.getByText("Questions to discuss")).toBeVisible();
    expect(
      screen.getByText(/what is the current expected close date/i),
    ).toBeVisible();
    fireEvent.click(screen.getByText("Why this question?"));
    expect(screen.getAllByText(reason.explanation).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Current Opportunity state").length,
    ).toBeGreaterThan(0);
    expect(
      screen.queryByText(/transcript|leaderboard|coaching score/i),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Independent manager forecast"), {
      target: { value: "possible" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save new manager revision" }),
    );
    await waitFor(() =>
      expect(requests.some((request) => request.init?.method === "POST")).toBe(
        true,
      ),
    );
    const write = requests.find((request) => request.init?.method === "POST");
    expect(write?.url).toContain("/manager-judgments");
    expect(JSON.parse(String(write?.init?.body))).toMatchObject({
      category: "possible",
      expectedRevisionNumber: 1,
    });
  });
});
