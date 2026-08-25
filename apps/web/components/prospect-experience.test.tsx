import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountPublicResearch } from "@/components/account-public-research";
import { ProspectFind } from "@/components/prospect-find";
import { ProspectModuleSettings } from "@/components/prospect-module-settings";
import { ProspectResearchBriefView } from "@/components/prospect-research-brief";

const navigation = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
}));

function jsonResponse(payload: object, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const availability = {
  moduleKey: "prospect",
  state: "available",
  enabled: true,
  canManage: true,
  message: "RevenueOS Prospect is available for this organisation.",
};

const target = {
  id: "target-1",
  name: "Northstar Facilities Group",
  domain: "northstar-facilities.example",
  websiteUrl: "https://northstar-facilities.example/",
  location: "Sydney, Australia",
  industry: "Facilities services",
  providerAttribution: "RevenueOS synthetic research data",
  promotedCompanyId: null,
  promotedAt: null,
  createdAt: "2026-08-25T01:00:00Z",
  updatedAt: "2026-08-25T01:02:00Z",
};

const sources = [
  {
    id: "source-official",
    sourceType: "company_newsroom",
    url: "https://northstar-facilities.example/news/expansion",
    canonicalUrl: "https://northstar-facilities.example/news/expansion",
    domain: "northstar-facilities.example",
    title: "Northstar expands Australian operations",
    publisher: "Northstar Newsroom",
    publishedAt: "2026-05-14T00:00:00Z",
    retrievedAt: "2026-08-25T01:02:00Z",
    authorityClass: "official_public",
  },
  {
    id: "source-provider",
    sourceType: "structured_provider",
    url: "https://mock-provider.example/company/northstar",
    canonicalUrl: "https://mock-provider.example/company/northstar",
    domain: "mock-provider.example",
    title: "Synthetic company profile",
    publisher: "Synthetic provider",
    publishedAt: null,
    retrievedAt: "2026-08-25T01:02:00Z",
    authorityClass: "structured_provider",
  },
];

const observations = [
  {
    id: "observation-profile",
    observationKey: "company_profile",
    category: "company_profile",
    statement:
      "Northstar manages facilities operations across 18 Australian sites.",
    trustState: "verified",
    relevance: "normal",
    observedAt: null,
    freshness: "stable",
    sourceIds: ["source-official"],
  },
  {
    id: "observation-expansion",
    observationKey: "expansion",
    category: "expansion",
    statement:
      "Northstar announced expansion into three additional Australian locations.",
    trustState: "verified",
    relevance: "high",
    observedAt: "2026-05-14T00:00:00Z",
    freshness: "time_sensitive",
    sourceIds: ["source-official"],
  },
  {
    id: "observation-size",
    observationKey: "employee_band",
    category: "size",
    statement: "The provider reports an employee band of 500–1,000.",
    trustState: "provider_supplied",
    relevance: "normal",
    observedAt: null,
    freshness: "time_sensitive",
    sourceIds: ["source-provider"],
  },
  {
    id: "observation-fit",
    observationKey: "operational_complexity",
    category: "potential_fit",
    statement:
      "Multi-site growth may increase operational complexity worth exploring.",
    trustState: "inferred",
    relevance: "high",
    observedAt: null,
    freshness: "time_sensitive",
    sourceIds: ["source-official"],
  },
  {
    id: "observation-unknown",
    observationKey: "technology_budget",
    category: "technology",
    statement: "Northstar's technology budget could not be established.",
    trustState: "unknown",
    relevance: "normal",
    observedAt: null,
    freshness: "time_sensitive",
    sourceIds: [],
  },
];

function researchBrief(overrides: Record<string, object> = {}) {
  const run = {
    id: "run-1",
    status: "completed",
    refreshOfRunId: null,
    createdAt: "2026-08-25T01:00:00Z",
    startedAt: "2026-08-25T01:01:00Z",
    completedAt: "2026-08-25T01:02:00Z",
    sourceCount: 2,
    observationCount: 5,
    errorCode: null,
  };
  return {
    target,
    status: "ready",
    statusMessage: "Research ready.",
    currentRun: run,
    latestRun: run,
    observations,
    sources,
    changes: [],
    history: [run],
    existingCompanyMatch: null,
    ...overrides,
  };
}

describe("RevenueOS Prospect experience", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    navigation.push.mockReset();
  });

  it("requires the user to resolve an ambiguous company before starting research", async () => {
    const candidates = [
      {
        candidateId: "northstar-facilities-group",
        name: "Northstar Facilities Group",
        domain: "northstar-facilities.example",
        websiteUrl: "https://northstar-facilities.example/",
        location: "Sydney, Australia",
        industry: "Facilities services",
        providerAttribution: "RevenueOS synthetic research data",
      },
      {
        candidateId: "northstar-software",
        name: "Northstar Software",
        domain: "northstar-software.example",
        websiteUrl: "https://northstar-software.example/",
        location: "Melbourne, Australia",
        industry: "Business software",
        providerAttribution: "RevenueOS synthetic research data",
      },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/prospect/availability"))
        return jsonResponse(availability);
      if (url.endsWith("/prospect/research") && !init?.method)
        return jsonResponse({ items: [] });
      if (url.includes("/prospect/companies/search"))
        return jsonResponse({
          items: candidates,
          query: "Northstar",
          ambiguous: true,
        });
      if (url.endsWith("/prospect/research") && init?.method === "POST")
        return jsonResponse(researchBrief(), 202);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ProspectFind />);
    expect(
      await screen.findByText("Which company are you looking for?"),
    ).toBeVisible();
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search company name or website" }),
      { target: { value: "Northstar" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Search companies" }));

    expect(
      await screen.findByText(/More than one company matches/i),
    ).toBeVisible();
    expect(screen.getByText("northstar-facilities.example")).toBeVisible();
    expect(screen.getByText("northstar-software.example")).toBeVisible();
    const facilityCard = screen
      .getByText("Northstar Facilities Group")
      .closest("article");
    fireEvent.click(
      within(facilityCard!).getByRole("button", { name: "Research company" }),
    );
    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith("/find/target-1"),
    );
  });

  it("shows a restrained unavailable state without hiding existing Accounts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        jsonResponse({ ...availability, state: "not_in_plan", enabled: false }),
      ),
    );
    render(<ProspectFind />);
    expect(
      await screen.findByText(/not available in this workspace/i),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "View Accounts" })).toHaveAttribute(
      "href",
      "/companies",
    );
    expect(screen.queryByText(/buy|price|upgrade/i)).not.toBeInTheDocument();
  });

  it("renders exact trust labels, safe sources, change history and explicit promotion", async () => {
    const refreshed = researchBrief({
      changes: [
        {
          changeType: "new",
          observationKey: "sydney_operations_centre",
          statement: "Northstar announced a new Sydney operations centre.",
          previousStatement: null,
        },
      ],
    });
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => jsonResponse(researchBrief()))
      .mockImplementationOnce(() => jsonResponse(refreshed, 202))
      .mockImplementationOnce(() =>
        jsonResponse({
          status: "created",
          companyId: "company-1",
          companyName: "Northstar Facilities Group",
          researchTargetId: "target-1",
          message:
            "The account was added to Sales. No opportunity or contact was created.",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ProspectResearchBriefView targetId="target-1" />);

    expect(
      await screen.findByRole("heading", {
        name: "Northstar Facilities Group",
      }),
    ).toBeVisible();
    for (const label of [
      "Verified",
      "From data provider",
      "RevenueOS inference",
      "Not established",
    ]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(/not customer-confirmed needs/i)).toBeVisible();
    const sourceLink = screen.getAllByRole("link", { name: /Open source/i })[0];
    expect(sourceLink).toHaveAttribute("target", "_blank");
    expect(sourceLink).toHaveAttribute("rel", "noopener noreferrer");
    expect(sourceLink).toHaveAttribute("referrerpolicy", "no-referrer");

    fireEvent.click(screen.getByRole("button", { name: "Refresh research" }));
    expect(
      await screen.findByRole("heading", { name: "What changed" }),
    ).toBeVisible();
    expect(
      screen.getByText("Northstar announced a new Sydney operations centre."),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Add to Sales" }));
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByText(/will not create an Opportunity or Contact/i),
    ).toBeVisible();
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Add account" }),
    );
    expect(
      await screen.findByRole("link", { name: "Open account" }),
    ).toHaveAttribute("href", "/companies/company-1");
    expect(
      screen.getByText(/No opportunity or contact was created/i),
    ).toBeVisible();
  });

  it("keeps public research visibly separate on the canonical Account", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        jsonResponse({
          targetId: "target-1",
          companyId: "company-1",
          updatedAt: "2026-08-25T01:02:00Z",
          status: "ready",
        }),
      ),
    );
    render(<AccountPublicResearch companyId="company-1" />);
    expect(
      await screen.findByText("Separate from customer evidence"),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "View research" })).toHaveAttribute(
      "href",
      "/find/target-1",
    );
  });

  it("lets an administrator toggle the server-authoritative module entitlement", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => jsonResponse(availability))
      .mockImplementationOnce(() =>
        jsonResponse({ ...availability, state: "not_in_plan", enabled: false }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ProspectModuleSettings />);
    const toggle = await screen.findByRole("switch", { name: "Enabled" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    fireEvent.click(toggle);
    expect(
      await screen.findByRole("switch", { name: "Disabled" }),
    ).toHaveAttribute("aria-checked", "false");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "PATCH" });
  });
});
