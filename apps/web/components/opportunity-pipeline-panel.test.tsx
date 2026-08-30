import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OpportunityPipelinePanel } from "@/components/opportunity-pipeline-panel";

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
    guidance: null,
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

const baseline = {
  id: "event-initial",
  fromPipelineId: null,
  toPipelineId: "pipeline-1",
  fromStageId: null,
  toStageId: "stage-discovery",
  fromStageName: null,
  toStageName: "Discovery",
  fromStageType: null,
  toStageType: "open",
  changedByUserId: null,
  changedByName: null,
  changedAt: "2026-08-30T00:00:00Z",
  source: "migration_baseline",
  isBaseline: true,
  previousStageEnteredAt: null,
  outcomeReason: null,
  outcomeNote: null,
  outcomeProvenance: null,
  actualCloseDate: null,
  finalAmount: null,
  finalCurrency: null,
};

function state(overrides: Record<string, unknown> = {}) {
  return {
    opportunityId: "opportunity-1",
    status: "open",
    pipeline,
    stage: stages[0],
    stageEnteredAt: null,
    stageTrackingStartedAt: "2026-08-30T00:00:00Z",
    daysInStage: null,
    actualCloseDate: null,
    outcomeReason: null,
    outcomeNote: null,
    outcomeProvenance: null,
    availablePipelines: [pipeline],
    history: [baseline],
    stageChangesAllowed: true,
    managedExternally: false,
    authorityMessage: null,
    ...overrides,
  };
}

describe("OpportunityPipelinePanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("closes Lost, labels seller-reported history and reopens without erasing it", async () => {
    const lostEvent = {
      ...baseline,
      id: "event-lost",
      fromPipelineId: "pipeline-1",
      fromStageId: "stage-discovery",
      toStageId: "stage-lost",
      fromStageName: "Discovery",
      toStageName: "Closed Lost",
      fromStageType: "open",
      toStageType: "lost",
      changedByUserId: "user-1",
      changedByName: "Alex Morgan",
      source: "manual",
      isBaseline: false,
      previousStageEnteredAt: "2026-08-28T00:00:00Z",
      outcomeReason: "timing",
      outcomeNote: "Customer timing changed.",
      outcomeProvenance: "seller_reported",
      actualCloseDate: "2026-08-30",
      finalAmount: "125000.50",
      finalCurrency: "AUD",
    };
    const closed = state({
      status: "lost",
      stage: stages[3],
      stageEnteredAt: "2026-08-30T01:00:00Z",
      daysInStage: 0,
      actualCloseDate: "2026-08-30",
      outcomeReason: "timing",
      outcomeNote: "Customer timing changed.",
      outcomeProvenance: "seller_reported",
      history: [baseline, lostEvent],
    });
    const reopened = state({
      stageEnteredAt: "2026-08-30T02:00:00Z",
      daysInStage: 0,
      history: [baseline, lostEvent],
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/close-lost") && init?.method === "POST") {
        return Promise.resolve(response(closed));
      }
      if (url.endsWith("/reopen") && init?.method === "POST") {
        return Promise.resolve(response(reopened));
      }
      return Promise.resolve(response(state()));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityPipelinePanel opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", { name: "Discovery" }),
    ).toBeVisible();
    fireEvent.click(screen.getByText("Stage history"));
    expect(
      screen.getByText(/Earlier stage history is unavailable/),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Mark Lost" }));
    fireEvent.change(screen.getByLabelText("Why was this opportunity lost?"), {
      target: { value: "timing" },
    });
    fireEvent.change(
      screen.getByLabelText("Internal outcome note (optional)"),
      {
        target: { value: "Customer timing changed." },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Close Lost" }));

    expect(await screen.findByText("Timing · seller reported")).toBeVisible();
    const closeCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).endsWith("/close-lost"),
    );
    expect(JSON.parse(String(closeCall?.[1]?.body))).toMatchObject({
      outcomeReason: "timing",
      outcomeNote: "Customer timing changed.",
    });

    fireEvent.click(screen.getByRole("button", { name: "Reopen opportunity" }));
    fireEvent.click(screen.getByRole("button", { name: "Reopen" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Reopen opportunity" }),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("heading", { name: "Discovery" })).toBeVisible();
    expect(screen.getByText("Outcome: Timing · seller reported")).toBeVisible();
    expect(screen.getByText("2 days in the previous stage")).toBeVisible();
    expect(
      screen.getByText(/Actual close 30 Aug 2026.*\$125,001/),
    ).toBeVisible();
  });

  it("keeps the close dialog open when the safe API request fails", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(
          response(
            {
              code: "stale_pipeline_state",
              message: "This opportunity changed. Refresh to continue.",
              requestId: "request-1",
            },
            409,
          ),
        );
      }
      return Promise.resolve(response(state()));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityPipelinePanel opportunityId="opportunity-1" />);

    await screen.findByRole("heading", { name: "Discovery" });
    fireEvent.click(screen.getByRole("button", { name: "Mark Won" }));
    fireEvent.click(screen.getByRole("button", { name: "Close Won" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This opportunity changed. Refresh to continue.",
    );
    expect(screen.getByRole("dialog", { name: "Mark as Won" })).toBeVisible();
  });
});
