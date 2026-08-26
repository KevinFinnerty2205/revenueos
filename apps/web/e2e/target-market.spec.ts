import { expect, test } from "@playwright/test";

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
  id: "run-wo-028",
  targetMarketId: "market-wo-028",
  targetMarketVersionId: "version-wo-028",
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
  id: "market-wo-028",
  name: "Australian Multi-Site Enterprises",
  status: "active",
  currentVersion: 1,
  canManage: true,
  definition: {
    id: "version-wo-028",
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

const candidateBase = {
  saved: false,
  excludedByUser: false,
  exclusionReason: null,
  researchStatus: "not_started",
  activeOpportunityId: null,
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
      ...candidateBase,
      id: "candidate-northstar",
      prospectTargetId: "target-northstar",
      providerCandidateId: "northstar-facilities-group",
      companyName: "Northstar Facilities Group",
      domain: "northstar-facilities.example",
      location: "Sydney, Australia",
      industry: "Facilities services",
      employeeBand: "1000_4999",
      matchState: "match",
      priority: "high",
      relationshipState: "new_prospect",
      matchedCompanyId: null,
      missingInformation: [],
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
      ],
    },
    {
      ...candidateBase,
      id: "candidate-harbour",
      prospectTargetId: "target-harbour",
      providerCandidateId: "harbour-health-network",
      companyName: "Harbour Health Network",
      domain: "harbour-health.example",
      location: "Newcastle, Australia",
      industry: "Healthcare",
      employeeBand: null,
      matchState: "partial",
      priority: "needs_more_information",
      relationshipState: "existing_account_no_active_opportunity",
      matchedCompanyId: "company-harbour",
      missingInformation: ["Company size could not be established."],
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
    },
    {
      ...candidateBase,
      id: "candidate-southbank",
      prospectTargetId: "target-southbank",
      providerCandidateId: "southbank-retail-group",
      companyName: "Southbank Retail Group",
      domain: "southbank-retail.example",
      location: "Melbourne, Australia",
      industry: "Retail",
      employeeBand: "500_999",
      matchState: "excluded",
      priority: "excluded",
      relationshipState: "new_prospect",
      matchedCompanyId: null,
      missingInformation: [],
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
    },
  ],
  message: "Accounts ready",
  highPriorityExplanation:
    "Strong fit with your targeting criteria; not purchase intent",
};

test("creates a Target Market and reviews explainable account whitespace", async ({
  page,
}) => {
  let created = false;
  let saved = false;
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({
        json: {
          featureFlags: { revenueBrain: false, prospect: true },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
      return;
    }
    if (path === "/api/v1/prospect/availability") {
      await route.fulfill({
        json: {
          moduleKey: "prospect",
          state: "available",
          enabled: true,
          canManage: true,
          message: "RevenueOS Prospect is available for this organisation.",
        },
      });
      return;
    }
    if (path === "/api/v1/prospect/discovery/capabilities") {
      await route.fulfill({ json: capabilities });
      return;
    }
    if (
      path === "/api/v1/prospect/target-markets" &&
      request.method() === "POST"
    ) {
      expect(request.postDataJSON()).toMatchObject({
        name: market.name,
        industries: ["Facilities services"],
        countries: ["AU"],
        minimumEmployeeBand: "500_999",
        preferredBusinessCharacteristics: ["multi_site"],
        excludedIndustries: ["Retail"],
      });
      created = true;
      await route.fulfill({
        status: 201,
        json: { ...market, latestRun: null, recentRuns: [] },
      });
      return;
    }
    if (path === `/api/v1/prospect/target-markets/${market.id}`) {
      await route.fulfill({
        json: created ? { ...market, latestRun: null, recentRuns: [] } : market,
      });
      return;
    }
    if (path === `/api/v1/prospect/target-markets/${market.id}/discover`) {
      await route.fulfill({ status: 202, json: discovery });
      return;
    }
    if (path === "/api/v1/prospect/discovery/run-wo-028") {
      await route.fulfill({ json: discovery });
      return;
    }
    if (path === "/api/v1/prospect/candidates/candidate-northstar/save") {
      saved = true;
      await route.fulfill({
        json: {
          prospectTargetId: "target-northstar",
          saved: true,
          excludedByUser: false,
          exclusionReason: null,
        },
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { message: `Unhandled ${path}` },
    });
  });

  await page.goto("/find/target-markets/new");
  await page.getByLabel("Target market name").fill(market.name);
  await page.getByLabel("Facilities services").first().check();
  await page.getByLabel(/Minimum company size/u).selectOption("500_999");
  await page.getByLabel("Multi-site").check();
  await page.getByLabel("Retail").last().check();
  await page.getByRole("button", { name: "Create target market" }).click();
  await expect(page).toHaveURL(`/find/target-markets/${market.id}`);
  await expect(page.getByRole("heading", { name: market.name })).toBeVisible();

  await page.getByRole("button", { name: "Find accounts" }).click();
  await expect(page.getByText("3 discovered accounts")).toBeVisible();
  await expect(
    page.getByText(/does not mean the company intends to buy/u),
  ).toBeVisible();
  await expect(page.getByText("Northstar Facilities Group")).toBeVisible();
  await expect(page.getByText("Harbour Health Network")).toBeVisible();
  await expect(
    page.getByText("Already in Sales · no active opportunity"),
  ).toBeVisible();

  const northstar = page
    .getByRole("article")
    .filter({ hasText: "Northstar Facilities Group" });
  await northstar.getByRole("button", { name: "Save" }).click();
  await expect(northstar.getByRole("button", { name: "Saved" })).toBeVisible();
  expect(saved).toBe(true);

  await page.getByRole("button", { name: "Excluded / unknown" }).click();
  await expect(page.getByText("Southbank Retail Group")).toBeVisible();
  await expect(page.getByText("Excluded industry: Retail.")).toBeVisible();
});
