import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ProspectTargetMarketBuilder,
  ProspectTargetMarketDetail,
} from "@/components/prospect-target-market";

const navigation = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));

function jsonResponse(payload: object, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const capabilities = {
  industries: [
    "Business software",
    "Facilities services",
    "Healthcare",
    "Retail",
  ],
  countries: ["AU", "NZ"],
  regions: ["NSW", "VIC", "QLD"],
  employeeBands: ["50_199", "200_499", "500_999", "1000_4999", "5000_plus"],
  organisationTypes: ["private_company", "public_company", "healthcare"],
  businessCharacteristics: [
    "multi_site",
    "international",
    "expanding",
    "regulated",
    "b2b",
  ],
  maxCandidatesPerRun: 50,
  maxActiveTargetMarkets: 10,
  liveData: false,
  message:
    "Synthetic account discovery is available for private-beta evaluation.",
};

const run = {
  id: "run-1",
  targetMarketId: "market-1",
  targetMarketVersionId: "version-1",
  targetMarketVersion: 1,
  status: "completed",
  requestedAt: "2026-08-26T01:00:00Z",
  startedAt: "2026-08-26T01:00:00Z",
  completedAt: "2026-08-26T01:00:01Z",
  candidateCount: 3,
  eligibleCount: 1,
  excludedCount: 1,
  partialCount: 1,
  failureCode: null,
  refreshedFromRunId: null,
};

const market = {
  id: "market-1",
  name: "Australian Multi-Site Enterprises",
  status: "active",
  currentVersion: 1,
  canManage: true,
  definition: {
    id: "version-1",
    version: 1,
    description: "Large Australian organisations with distributed operations.",
    industries: ["Facilities services", "Healthcare"],
    countries: ["AU"],
    regions: [],
    minimumEmployeeBand: "500_999",
    organisationTypes: [],
    preferredBusinessCharacteristics: ["multi_site"],
    excludedIndustries: ["Retail"],
    excludeExistingAccounts: false,
    researchObjective: "Access-control opportunity",
    createdAt: "2026-08-26T00:00:00Z",
  },
  latestRun: run,
  recentRuns: [run],
  createdAt: "2026-08-26T00:00:00Z",
  updatedAt: "2026-08-26T00:00:00Z",
};

const discovery = {
  targetMarket: market,
  run,
  summary: {
    totalCandidates: 3,
    highPriority: 1,
    worthResearching: 0,
    needsMoreInformation: 1,
    excluded: 1,
    existingAccounts: 1,
    activeOpportunities: 0,
    newProspects: 2,
  },
  candidates: [
    {
      id: "candidate-1",
      prospectTargetId: "target-1",
      providerCandidateId: "northstar-facilities-group",
      companyName: "Northstar Facilities Group",
      domain: "northstar-facilities.example",
      location: "Sydney, Australia",
      industry: "Facilities services",
      employeeBand: "1000_4999",
      matchState: "match",
      priority: "high",
      reasons: [
        {
          reasonCode: "industry_match",
          criterionKey: "industries",
          state: "matched",
          text: "Matches your Facilities services industry criterion.",
          dataOrigin: "provider_supplied",
          trustState: "provider_supplied",
          observedValueClass: "Facilities services",
          sourceReference: null,
        },
        {
          reasonCode: "public_trigger_context",
          criterionKey: "current_public_context",
          state: "context",
          text: "Northstar announced expansion into three additional Australian locations.",
          dataOrigin: "provider_supplied",
          trustState: "provider_supplied",
          observedValueClass: "time_sensitive_public_context",
          sourceReference:
            "https://northstar-facilities.example/news/australian-expansion",
        },
      ],
      missingInformation: [],
      relationshipState: "new_prospect",
      matchedCompanyId: null,
      activeOpportunityId: null,
      saved: false,
      excludedByUser: false,
      exclusionReason: null,
      researchStatus: "not_started",
    },
    {
      id: "candidate-2",
      prospectTargetId: "target-2",
      providerCandidateId: "harbour-health-network",
      companyName: "Harbour Health Network",
      domain: "harbour-health.example",
      location: "Newcastle, Australia",
      industry: "Healthcare",
      employeeBand: null,
      matchState: "partial",
      priority: "needs_more_information",
      reasons: [
        {
          reasonCode: "unknown_size",
          criterionKey: "minimum_employee_band",
          state: "missing",
          text: "Company size could not be established.",
          dataOrigin: "unknown",
          trustState: "unknown",
          observedValueClass: null,
          sourceReference: null,
        },
      ],
      missingInformation: ["Company size could not be established."],
      relationshipState: "existing_account_no_active_opportunity",
      matchedCompanyId: "company-2",
      activeOpportunityId: null,
      saved: false,
      excludedByUser: false,
      exclusionReason: null,
      researchStatus: "not_started",
    },
    {
      id: "candidate-3",
      prospectTargetId: "target-3",
      providerCandidateId: "southbank-retail-group",
      companyName: "Southbank Retail Group",
      domain: "southbank-retail.example",
      location: "Melbourne, Australia",
      industry: "Retail",
      employeeBand: "500_999",
      matchState: "excluded",
      priority: "excluded",
      reasons: [
        {
          reasonCode: "excluded_industry",
          criterionKey: "excluded_industries",
          state: "excluded",
          text: "Excluded industry: Retail.",
          dataOrigin: "provider_supplied",
          trustState: "provider_supplied",
          observedValueClass: "Retail",
          sourceReference: null,
        },
      ],
      missingInformation: [],
      relationshipState: "new_prospect",
      matchedCompanyId: null,
      activeOpportunityId: null,
      saved: false,
      excludedByUser: false,
      exclusionReason: null,
      researchStatus: "not_started",
    },
  ],
  message: "Accounts ready",
  highPriorityExplanation:
    "Strong fit with your targeting criteria; not purchase intent",
};

describe("Prospect Target Market experience", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    navigation.push.mockReset();
  });

  it("guides an admin through supported Target Market criteria", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/prospect/discovery/capabilities"))
        return jsonResponse(capabilities);
      if (url.endsWith("/prospect/target-markets") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        expect(body).toMatchObject({
          name: "Australian Multi-Site Enterprises",
          industries: ["Facilities services"],
          countries: ["AU"],
          minimumEmployeeBand: "500_999",
          preferredBusinessCharacteristics: ["multi_site"],
          excludedIndustries: ["Retail"],
        });
        return jsonResponse(
          { ...market, latestRun: null, recentRuns: [] },
          201,
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ProspectTargetMarketBuilder />);
    expect(
      await screen.findByText("Who do you want to sell to?"),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Target market name"), {
      target: { value: "Australian Multi-Site Enterprises" },
    });
    fireEvent.click(screen.getAllByLabelText("Facilities services")[0]);
    fireEvent.change(screen.getByLabelText(/Minimum company size/i), {
      target: { value: "500_999" },
    });
    fireEvent.click(screen.getByLabelText("Multi-site"));
    fireEvent.click(screen.getAllByLabelText("Retail").at(-1)!);
    fireEvent.click(
      screen.getByRole("button", { name: "Create target market" }),
    );

    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith(
        "/find/target-markets/market-1",
      ),
    );
  });

  it("shows explainable priority, unknown, whitespace, exclusion and research actions", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/prospect/target-markets/market-1") && !init?.method)
        return jsonResponse(market);
      if (url.endsWith("/prospect/discovery/run-1"))
        return jsonResponse(discovery);
      if (url.endsWith("/prospect/candidates/candidate-1/save"))
        return jsonResponse({
          prospectTargetId: "target-1",
          saved: true,
          excludedByUser: false,
          exclusionReason: null,
        });
      if (url.endsWith("/prospect/research") && init?.method === "POST")
        return jsonResponse({ target: { id: "target-1" } }, 202);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ProspectTargetMarketDetail marketId="market-1" />);
    expect(await screen.findByText("Northstar Facilities Group")).toBeVisible();
    expect(screen.getAllByText("High priority").length).toBeGreaterThan(1);
    expect(
      screen.getByText(/does not mean the company intends to buy/i),
    ).toBeVisible();
    expect(screen.queryByText(/\d+%/u)).not.toBeInTheDocument();
    expect(screen.getByText("Harbour Health Network")).toBeVisible();
    expect(screen.getByText(/Already in Sales/i)).toBeVisible();
    expect(
      screen.queryByText("Southbank Retail Group"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Excluded / unknown" }));
    expect(screen.getByText("Southbank Retail Group")).toBeVisible();
    expect(screen.getByText("Excluded industry: Retail.")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Matches" }));
    const northstarCard = screen
      .getByText("Northstar Facilities Group")
      .closest("article");
    fireEvent.click(
      within(northstarCard!).getByRole("button", { name: "Save target" }),
    );
    expect(
      await within(northstarCard!).findByRole("button", {
        name: "Remove saved",
      }),
    ).toBeVisible();
    fireEvent.click(
      within(northstarCard!).getByRole("button", { name: "Research" }),
    );
    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith("/find/target-1"),
    );
  });
});
