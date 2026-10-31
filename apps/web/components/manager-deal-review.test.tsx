import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ManagerDealReview } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ManagerDealReviewPanel } from "@/components/manager-deal-review";

function response(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const review: ManagerDealReview = {
  deal: {
    opportunityId: "opportunity-1",
    opportunityName: "Northstar rollout",
    companyName: "Northstar Facilities",
    ownerUserId: "user-1",
    ownerDisplayName: "Alex Morgan",
    pipelineId: "pipeline-1",
    pipelineName: "Direct sales",
    stageId: "stage-1",
    stageName: "Proposal",
    amount: "125000",
    currency: "AUD",
    expectedCloseDate: "2026-11-30",
    sellerForecast: null,
    managerForecast: null,
    reasons: [],
    href: "/opportunities/opportunity-1",
  },
  historicalBaseline: {
    state: "insufficient_sample",
    expectedContribution: null,
    wonCount: 0,
    lostCount: 0,
    explanation: "Not enough closed history is available.",
  },
  methodologyGaps: [],
  currentActions: [],
  latestInteraction: null,
  recentChanges: [],
  questions: [],
  generatedAt: "2026-10-25T00:00:00Z",
};

describe("ManagerDealReviewPanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("links back to seller evidence without mislabelling the workspace as Sales Brain", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(review)));

    render(<ManagerDealReviewPanel opportunityId="opportunity-1" />);

    fireEvent.click(
      await screen.findByText("Manager review and forecast", {
        selector: "summary",
      }),
    );
    expect(
      await screen.findByRole("link", { name: "Review seller evidence" }),
    ).toHaveAttribute("href", "#deal-methodology");
    expect(
      screen.queryByRole("link", { name: "Open Sales Brain" }),
    ).not.toBeInTheDocument();
  });

  it("does not expose manager-only controls when the current user is not authorised", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          {
            code: "forbidden",
            message: "Manager access is required.",
            requestId: "request-1",
          },
          403,
        ),
      ),
    );

    render(<ManagerDealReviewPanel opportunityId="opportunity-1" />);

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(
      screen.queryByText("Manager review and forecast"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Independent manager forecast"),
    ).not.toBeInTheDocument();
  });
});
