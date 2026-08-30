import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SalesInsights } from "@/components/sales-insights";

const pipelineId = "11111111-1111-4111-8111-111111111111";
const ownerId = "owner-1";

const scope = {
  startDate: "2026-07-01",
  endDate: "2026-08-30",
  timezone: "Australia/Sydney",
  pipelineId: null,
  ownerUserId: null,
  generatedAt: "2026-08-30T03:00:00Z",
};

const metadata = {
  currentUserId: "22222222-2222-4222-8222-222222222222",
  pipelines: [
    {
      id: pipelineId,
      name: "New business",
      isDefault: true,
      active: true,
      stages: [
        {
          id: "stage-1",
          name: "Discovery",
          position: 1,
          stageType: "open",
          active: true,
        },
        {
          id: "stage-2",
          name: "Won",
          position: 2,
          stageType: "won",
          active: true,
        },
      ],
    },
  ],
  owners: [{ userId: ownerId, displayName: "Alex Seller", active: true }],
  metrics: [],
  outcomeWindowDays: 30,
  maximumRangeDays: 1827,
  generatedAt: "2026-08-30T03:00:00Z",
};

const targetMetadata = {
  currentUserId: "22222222-2222-4222-8222-222222222222",
  currentUserRole: "member",
  organisationTimezone: "Australia/Sydney",
  metrics: [],
  owners: [],
  pipelines: [],
  canAssignPersonalTargets: false,
  canCreateOrganisationTargets: false,
};

const emptyTargets = {
  items: [],
  canAssignPersonalTargets: false,
  canCreateOrganisationTargets: false,
  maximumVisibleTargets: 200,
};

const overview = {
  scope,
  openOpportunityCount: 3,
  opportunitiesCreatedCount: 5,
  wonCount: 2,
  lostCount: 1,
  closedCount: 3,
  winRate: "66.7",
  medianSalesCycleDays: "24.0",
  wonValues: [
    { currency: "AUD", amount: "125000.00", opportunityCount: 1 },
    { currency: "USD", amount: "50000.00", opportunityCount: 1 },
  ],
  unvaluedWonCount: 0,
  hasOpportunities: true,
};

const funnel = {
  scope: { ...scope, pipelineId },
  pipelineId,
  pipelineName: "New business",
  cohortDefinition:
    "First reliable entry into this pipeline during the selected local-date range.",
  cohortCount: 4,
  currentOpenCount: 1,
  currentWonCount: 2,
  currentLostCount: 1,
  stages: [
    {
      stageId: "stage-1",
      stageName: "Discovery",
      position: 1,
      enteredCount: 4,
      advancedCount: 3,
      stillOpenCount: 0,
      closedLostCount: 1,
      otherNotAdvancedCount: 0,
      advanceRate: "75.0",
    },
    {
      stageId: "stage-2",
      stageName: "Won",
      position: 2,
      enteredCount: 2,
      advancedCount: 2,
      stillOpenCount: 0,
      closedLostCount: 0,
      otherNotAdvancedCount: 0,
      advanceRate: "100.0",
    },
  ],
  stageDurations: [
    {
      stageId: "stage-1",
      stageName: "Discovery",
      medianCompletedDays: "6.0",
      completedIntervalCount: 3,
    },
  ],
  coverage: {
    reliableOpportunityCount: 4,
    baselineOnlyOpportunityCount: 1,
    earliestReliableEventAt: "2026-07-04T02:00:00Z",
    disclosure: "Reliable history starts with non-baseline stage events.",
  },
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

const activity = {
  scope,
  phoneCallsCompletedCount: 4,
  meetingsCompletedCount: 3,
  callsFollowedByMeeting: followOn,
  meetingsFollowedByProgression: {
    ...followOn,
    rate: "33.3",
    followedByOutcomeCount: 1,
  },
  outreachAvailable: false,
  liveOutreachSentCount: 0,
  outreachFollowedByMeeting: null,
  associationDisclosure:
    "Records are associated through canonical account, opportunity or participant links.",
};

const winLoss = {
  scope,
  wonCount: 2,
  lostCount: 1,
  winRate: "66.7",
  wonReasons: [
    {
      reason: "product_fit",
      label: "Product fit",
      count: 2,
      percentage: "100.0",
    },
  ],
  lostReasons: [
    { reason: "budget", label: "Budget", count: 1, percentage: "100.0" },
  ],
  lossStages: [{ stageId: "stage-1", stageName: "Discovery", count: 1 }],
  salesCycles: [
    { outcome: "won", medianDays: "24.0", sampleSize: 2 },
    { outcome: "lost", medianDays: "30.0", sampleSize: 1 },
  ],
  values: [
    {
      outcome: "won",
      currency: "AUD",
      amount: "125000.00",
      medianAmount: "125000.00",
      opportunityCount: 1,
    },
  ],
  unvaluedWonCount: 0,
  unvaluedLostCount: 1,
  reasonProvenance: "seller_reported",
  notesAggregated: false,
};

function json(payload: object, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("sales insights", () => {
  it("loads filters and presents the five deterministic insight views", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/v1/beta/capabilities"))
        return json({ featureFlags: { salesTargets: true } });
      if (url.includes("/api/v1/targets/metadata")) return json(targetMetadata);
      if (url.includes("/api/v1/targets")) return json(emptyTargets);
      if (url.includes("/metadata")) return json(metadata);
      if (url.includes("/funnel")) return json(funnel);
      if (url.includes("/activity")) return json(activity);
      if (url.includes("/win-loss")) return json(winLoss);
      return json(overview);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<SalesInsights />);

    expect(await screen.findByText("Open opportunities")).toBeVisible();
    expect(screen.getByText("$125,000")).toBeVisible();
    expect(screen.getByText(/USD\s*50,000/u)).toBeVisible();
    expect(screen.getByText(/currencies remain separate/i)).toBeVisible();
    expect(await screen.findByText("Active targets")).toBeVisible();
    expect(screen.getByRole("tab", { name: "Targets" })).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Funnel" }));
    expect(screen.getByText(/choose one pipeline/i)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Pipeline"), {
      target: { value: pipelineId },
    });
    expect(await screen.findByText("New business progression")).toBeVisible();
    expect(screen.getByText(/skipped stages are not inferred/i)).toBeVisible();
    fireEvent.click(screen.getAllByText("View exact values")[0]);
    expect(
      within(
        screen.getByRole("table", { name: "Funnel exact values" }),
      ).getByText("75%"),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    expect(
      await screen.findByText("Calls followed by a meeting"),
    ).toBeVisible();
    expect(screen.getByText(/not causal attribution/i)).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Win / loss" }));
    expect(await screen.findByText("Why we won")).toBeVisible();
    expect(screen.getAllByText("Product fit")[0]).toBeVisible();
    expect(
      screen.getByText(/free-text win\/loss notes are intentionally excluded/i),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Targets" }));
    expect(
      await screen.findByRole("heading", { name: "Targets" }),
    ).toBeVisible();
    expect(
      screen.queryByLabelText("Sales insight filters"),
    ).not.toBeInTheDocument();

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("pipelineId="),
        expect.any(Object),
      ),
    );
  });

  it("shows a safe retry state when the read model is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => json({ message: "Analytics are unavailable." }, 503)),
    );
    render(<SalesInsights />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sales insights are unavailable",
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  it("does not expose Targets when the server capability is off", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/v1/beta/capabilities"))
        return json({ featureFlags: { salesTargets: false } });
      if (url.includes("/metadata")) return json(metadata);
      return json(overview);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<SalesInsights />);
    expect(await screen.findByText("Open opportunities")).toBeVisible();
    expect(
      screen.queryByRole("tab", { name: "Targets" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Active targets")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/targets"),
      expect.anything(),
    );
  });

  it("applies the exact date, timezone, Pipeline and owner from a Target deep link", async () => {
    window.history.replaceState(
      {},
      "",
      `/insights?tab=activity&metric=meetings_completed_count&startDate=2026-08-01&endDate=2026-08-30&timezone=Australia%2FSydney&pipelineId=${pipelineId}&ownerUserId=${ownerId}`,
    );
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/v1/beta/capabilities"))
        return json({ featureFlags: { salesTargets: true } });
      if (url.includes("/metadata")) return json(metadata);
      if (url.includes("/activity")) return json(activity);
      return json(overview);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<SalesInsights />);

    expect(await screen.findByText("Completed phone calls")).toBeVisible();
    expect(screen.getByRole("tab", { name: "Activity" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByLabelText("Date range")).toHaveValue("custom");
    expect(screen.getByLabelText("Start date")).toHaveValue("2026-08-01");
    expect(screen.getByLabelText("End date")).toHaveValue("2026-08-30");
    expect(screen.getByText("Australia/Sydney")).toBeVisible();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(
          /\/activity\?.*startDate=2026-08-01.*endDate=2026-08-30.*timezone=Australia%2FSydney.*pipelineId=.*ownerUserId=/u,
        ),
        expect.anything(),
      ),
    );
  });
});
