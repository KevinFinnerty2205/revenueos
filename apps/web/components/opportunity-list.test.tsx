import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OpportunityList } from "@/components/opportunity-list";

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

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
    guidance: null,
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
] as const;

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

function board(overrides: Record<string, unknown> = {}) {
  return {
    pipeline,
    pipelines: [pipeline],
    view: "open",
    summary: {
      openOpportunityCount: 2,
      needsAttentionCount: 1,
      closeDatesThisMonthCount: 1,
      unvaluedOpportunityCount: 0,
      values: [
        { currency: "AUD", amount: "125000.50", opportunityCount: 1 },
        { currency: "USD", amount: "50000.00", opportunityCount: 1 },
      ],
    },
    cards: [
      {
        opportunityId: "opportunity-1",
        opportunityName: "Platform expansion",
        companyId: "company-1",
        companyName: "Acme Australia",
        pipelineId: "pipeline-1",
        pipelineName: "RevenueOS Sales Pipeline",
        stageId: "stage-discovery",
        stageName: "Discovery",
        stageType: "open",
        status: "open",
        estimatedValue: "125000.50",
        currency: "AUD",
        expectedCloseDate: "2026-08-31",
        actualCloseDate: null,
        ownerUserId: "user-1",
        ownerName: "Alex Morgan",
        stageEnteredAt: "2026-08-28T00:00:00Z",
        stageTrackingStartedAt: "2026-08-28T00:00:00Z",
        daysInStage: 2,
        nextAction: "Confirm the procurement owner.",
        attentionReasons: ["Overdue high-priority Action"],
        outcomeReason: null,
        outcomeProvenance: null,
      },
      {
        opportunityId: "opportunity-2",
        opportunityName: "US pilot",
        companyId: "company-2",
        companyName: "Northwind",
        pipelineId: "pipeline-1",
        pipelineName: "RevenueOS Sales Pipeline",
        stageId: "stage-proposal",
        stageName: "Proposal",
        stageType: "open",
        status: "open",
        estimatedValue: "50000.00",
        currency: "USD",
        expectedCloseDate: "2026-09-30",
        actualCloseDate: null,
        ownerUserId: "user-2",
        ownerName: "Jordan Lee",
        stageEnteredAt: null,
        stageTrackingStartedAt: "2026-08-30T00:00:00Z",
        daysInStage: null,
        nextAction: null,
        attentionReasons: [],
        outcomeReason: null,
        outcomeProvenance: null,
      },
    ],
    stageChangesAllowed: true,
    managedExternally: false,
    authorityMessage: null,
    managerIntelligenceAvailable: false,
    generatedAt: "2026-08-30T01:00:00Z",
    ...overrides,
  };
}

describe("OpportunityList", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the board, deterministic attention and currency-safe summaries", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(board())));
    render(<OpportunityList />);

    expect(await screen.findAllByText("Platform expansion")).not.toHaveLength(
      0,
    );
    expect(screen.getAllByText("Acme Australia")).not.toHaveLength(0);
    expect(
      screen.getByText(
        (content) =>
          content.includes("$125,001") &&
          content.includes("USD") &&
          content.includes("50,000"),
      ),
    ).toBeVisible();
    expect(
      screen.getAllByText("Overdue high-priority Action"),
    ).not.toHaveLength(0);
    expect(screen.getAllByText("Tracking since 30 Aug 2026")).not.toHaveLength(
      0,
    );
    expect(
      screen.queryByText(/probability|weighted|health score/i),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "List" }));
    expect(
      screen.getByRole("columnheader", { name: "Time in stage" }),
    ).toBeVisible();
  });

  it("moves a card through the explicit accessible stage control", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(response({}));
      return Promise.resolve(response(board()));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityList />);

    const controls = await screen.findAllByLabelText("Move stage");
    fireEvent.change(controls[0], { target: { value: "stage-proposal" } });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => call[1]?.method === "POST"),
      ).toBe(true),
    );
    const moveCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "POST",
    );
    expect(String(moveCall?.[0])).toContain(
      "/api/v1/opportunities/opportunity-1/stage",
    );
    expect(JSON.parse(String(moveCall?.[1]?.body))).toMatchObject({
      targetStageId: "stage-proposal",
      expectedCurrentStageId: "stage-discovery",
    });
  });

  it("applies server-side search, owner and attention filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(board()));
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityList />);
    await screen.findAllByText("Platform expansion");

    fireEvent.change(screen.getByLabelText("Owner"), {
      target: { value: "user-1" },
    });
    fireEvent.click(screen.getByLabelText("Needs attention"));
    fireEvent.change(screen.getByLabelText("Search opportunity or account"), {
      target: { value: "Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes("ownerUserId=user-1"))).toBe(true);
      expect(urls.some((url) => url.includes("attentionOnly=true"))).toBe(true);
      expect(urls.some((url) => url.includes("search=Acme"))).toBe(true);
    });
  });

  it("makes external-CRM authority clear and removes move controls", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          board({
            stageChangesAllowed: false,
            managedExternally: true,
            authorityMessage: "Stages are managed in HubSpot.",
          }),
        ),
      ),
    );
    render(<OpportunityList />);

    expect(await screen.findByText("Managed in HubSpot.")).toBeVisible();
    expect(screen.queryByLabelText("Move stage")).not.toBeInTheDocument();
  });

  it("shows a recoverable safe error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response(
          {
            code: "persistence_unavailable",
            message: "Pipeline is temporarily unavailable.",
            requestId: "request-1",
          },
          503,
        ),
      )
      .mockResolvedValue(response(board({ cards: [] })));
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityList />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Pipeline is temporarily unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(
      await screen.findByRole("heading", { name: "No open opportunities" }),
    ).toBeVisible();
  });

  it("offers an explainable deal-centric manager view only when authorised", async () => {
    const attention = {
      total: 1,
      summaries: [
        { code: "close_date_passed", label: "Close date passed", dealCount: 1 },
      ],
      items: [
        {
          opportunityId: "opportunity-1",
          opportunityName: "Platform expansion",
          companyName: "Acme Australia",
          ownerUserId: "user-1",
          ownerDisplayName: "Alex Morgan",
          pipelineId: "pipeline-1",
          pipelineName: "RevenueOS Sales Pipeline",
          stageId: "stage-discovery",
          stageName: "Discovery",
          amount: "125000.50",
          currency: "AUD",
          expectedCloseDate: "2026-08-29",
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
          reasons: [
            {
              id: "close_date_passed:opportunity-1",
              code: "close_date_passed",
              label: "Close date passed",
              explanation:
                "The canonical expected close date is in the past while the Opportunity remains open.",
              detectedAt: "2026-08-30T00:00:00Z",
              sources: [
                {
                  sourceType: "opportunity",
                  sourceId: "opportunity-1",
                  label: "Current Opportunity state",
                  href: "/opportunities/opportunity-1",
                },
              ],
            },
          ],
          href: "/opportunities/opportunity-1",
        },
      ],
      page: 1,
      pageSize: 50,
      generatedAt: "2026-08-30T01:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          response(
            String(input).includes("/api/v1/manager/deal-attention")
              ? attention
              : board({ managerIntelligenceAvailable: true }),
          ),
        ),
      ),
    );
    render(<OpportunityList />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Manager view" }),
    );
    expect(
      await screen.findByText("Manager view · deals needing attention"),
    ).toBeVisible();
    expect(
      screen.getByText(/there is no health score or people ranking/i),
    ).toBeVisible();
    expect(screen.getByText("Seller view")).toBeVisible();
    expect(screen.getByText("Manager view", { selector: "dt" })).toBeVisible();
    expect(screen.queryByText(/leaderboard/i)).not.toBeInTheDocument();
  });
});
