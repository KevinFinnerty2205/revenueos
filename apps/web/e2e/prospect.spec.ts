import { expect, test, type Page } from "@playwright/test";

const availability = {
  moduleKey: "prospect",
  state: "available",
  enabled: true,
  canManage: true,
  executionMode: "demo",
  message: "RevenueOS Prospect is available for this organisation.",
};

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

const target = {
  id: "target-northstar",
  name: "Northstar Facilities Group",
  domain: "northstar-facilities.example",
  websiteUrl: "https://northstar-facilities.example/",
  location: "Sydney, Australia",
  industry: "Facilities services",
  providerAttribution: "RevenueOS synthetic research data",
  promotedCompanyId: null,
  promotedAt: null,
  createdAt: "2026-08-25T00:00:00Z",
  updatedAt: "2026-08-25T00:02:00Z",
};

const sources = [
  {
    id: "official-source",
    sourceType: "company_newsroom",
    url: "https://northstar-facilities.example/news/expansion",
    canonicalUrl: "https://northstar-facilities.example/news/expansion",
    domain: "northstar-facilities.example",
    title: "Northstar expands Australian operations",
    publisher: "Northstar Newsroom",
    publishedAt: "2026-05-14T00:00:00Z",
    retrievedAt: "2026-08-25T00:02:00Z",
    authorityClass: "official_public",
  },
  {
    id: "provider-source",
    sourceType: "structured_provider",
    url: "https://mock-provider.example/companies/northstar",
    canonicalUrl: "https://mock-provider.example/companies/northstar",
    domain: "mock-provider.example",
    title: "Synthetic company profile",
    publisher: "RevenueOS deterministic mock provider",
    publishedAt: null,
    retrievedAt: "2026-08-25T00:02:00Z",
    authorityClass: "structured_provider",
  },
];

const initialObservations = [
  observation(
    "company_profile",
    "company_profile",
    "Northstar Facilities Group manages facilities operations across 18 Australian sites.",
    "verified",
    ["official-source"],
  ),
  observation(
    "australian_expansion",
    "expansion",
    "Northstar announced expansion into three additional Australian locations in May 2026.",
    "verified",
    ["official-source"],
    "2026-05-14T00:00:00Z",
    "high",
  ),
  observation(
    "employee_band",
    "size",
    "The synthetic business-data provider reports an employee band of 500–1,000.",
    "provider_supplied",
    ["provider-source"],
  ),
  observation(
    "operational_complexity",
    "potential_fit",
    "Multi-site growth may increase operational complexity worth exploring in a discovery conversation.",
    "inferred",
    ["official-source"],
    null,
    "high",
  ),
  observation(
    "technology_budget",
    "technology",
    "Northstar's technology budget could not be established from public sources.",
    "unknown",
    [],
  ),
  observation(
    "infrastructure_hiring",
    "hiring",
    "Northstar's public careers page lists increased infrastructure hiring.",
    "verified",
    ["official-source"],
    null,
    "high",
  ),
];

function observation(
  observationKey: string,
  category: string,
  statement: string,
  trustState: string,
  sourceIds: string[],
  observedAt: string | null = null,
  relevance: "high" | "normal" = "normal",
) {
  return {
    id: `observation-${observationKey}`,
    observationKey,
    category,
    statement,
    trustState,
    relevance,
    observedAt,
    freshness: observedAt ? "time_sensitive" : "stable",
    sourceIds,
  };
}

function run(id: string, status: string, refreshOfRunId: string | null = null) {
  return {
    id,
    status,
    refreshOfRunId,
    createdAt: "2026-08-25T00:00:00Z",
    startedAt: status === "pending" ? null : "2026-08-25T00:01:00Z",
    completedAt: ["completed", "partial"].includes(status)
      ? "2026-08-25T00:02:00Z"
      : null,
    sourceCount: ["completed", "partial"].includes(status) ? sources.length : 0,
    observationCount: ["completed", "partial"].includes(status)
      ? initialObservations.length
      : 0,
    errorCode: null,
  };
}

function processingBrief() {
  const pending = run("run-initial", "fetching");
  return {
    target,
    status: "researching",
    statusMessage: "RevenueOS is checking permitted public business sources.",
    currentRun: null,
    latestRun: pending,
    observations: [],
    sources: [],
    changes: [],
    history: [pending],
    existingCompanyMatch: null,
  };
}

function failedBrief() {
  const failed = {
    ...run("run-failed", "failed"),
    completedAt: "2026-08-25T00:02:00Z",
    errorCode: "company_research_unavailable",
  };
  return {
    target,
    status: "failed",
    statusMessage:
      "RevenueOS couldn’t find enough reliable public information about this company.",
    currentRun: null,
    latestRun: failed,
    observations: [],
    sources: [],
    changes: [],
    history: [failed],
    existingCompanyMatch: null,
  };
}

function readyBrief(
  options: { refreshed?: boolean; existing?: boolean; partial?: boolean } = {},
) {
  const current = run(
    options.refreshed ? "run-refresh" : "run-initial",
    options.partial ? "partial" : "completed",
    options.refreshed ? "run-initial" : null,
  );
  const refreshedObservations = options.refreshed
    ? [
        ...initialObservations
          .filter((item) => item.observationKey !== "infrastructure_hiring")
          .map((item) =>
            item.observationKey === "employee_band"
              ? {
                  ...item,
                  statement:
                    "The synthetic business-data provider reports an employee band of 1,000–5,000.",
                }
              : item,
          ),
        observation(
          "sydney_operations_centre",
          "expansion",
          "Northstar announced a new Sydney operations centre in August 2026.",
          "verified",
          ["official-source"],
          "2026-08-20T00:00:00Z",
          "high",
        ),
      ]
    : initialObservations;
  return {
    target,
    status: options.partial ? "partial" : "ready",
    statusMessage: options.partial
      ? "RevenueOS found enough information for a partial brief, but some sources were unavailable."
      : "Research ready.",
    currentRun: current,
    latestRun: current,
    observations: options.partial
      ? initialObservations.slice(0, 2)
      : refreshedObservations,
    sources: options.partial ? sources.slice(0, 1) : sources,
    changes: options.refreshed
      ? [
          {
            changeType: "new",
            observationKey: "sydney_operations_centre",
            statement:
              "Northstar announced a new Sydney operations centre in August 2026.",
            previousStatement: null,
          },
          {
            changeType: "changed",
            observationKey: "employee_band",
            statement:
              "The synthetic business-data provider reports an employee band of 1,000–5,000.",
            previousStatement:
              "The synthetic business-data provider reports an employee band of 500–1,000.",
          },
          {
            changeType: "no_longer_supported",
            observationKey: "infrastructure_hiring",
            statement:
              "Northstar's public careers page lists increased infrastructure hiring.",
            previousStatement: null,
          },
        ]
      : [],
    history: options.refreshed
      ? [current, run("run-initial", "completed")]
      : [current],
    existingCompanyMatch: options.existing
      ? {
          id: "company-existing",
          name: "Northstar Facilities Group",
          domain: "northstar-facilities.example",
        }
      : null,
  };
}

const prospectPerson = {
  id: "person-jane",
  companyTargetId: target.id,
  displayName: "Jane Smith",
  currentRole: "Chief Technology Officer",
  currentCompany: target.name,
  publicProfessionalLocation: "Sydney, Australia",
  publicProfileUrl:
    "https://northstar-facilities.example/leadership/jane-smith",
  relevantFunction: "technology",
  whyMayMatter:
    "Her public remit suggests she may help evaluate operational technology change.",
  providerAttribution: "RevenueOS deterministic mock provider",
  identityState: "supported",
  employmentState: "current",
  researchStatus: "ready",
  promotedContactId: null,
  promotedAt: null,
  createdAt: "2026-08-25T00:00:00Z",
  updatedAt: "2026-08-25T00:02:00Z",
};

const personSource = {
  id: "person-source",
  sourceType: "company_leadership",
  url: "https://northstar-facilities.example/leadership/jane-smith",
  canonicalUrl: "https://northstar-facilities.example/leadership/jane-smith",
  domain: "northstar-facilities.example",
  title: "Jane Smith leadership profile",
  publisher: "Northstar Facilities Group",
  publishedAt: null,
  retrievedAt: "2026-08-25T00:02:00Z",
  authorityClass: "official_public",
};

function personResearchBrief() {
  const personRun = {
    id: "person-run",
    status: "completed",
    refreshOfRunId: null,
    createdAt: "2026-08-25T00:00:00Z",
    startedAt: "2026-08-25T00:01:00Z",
    completedAt: "2026-08-25T00:02:00Z",
    sourceCount: 1,
    observationCount: 3,
    errorCode: null,
  };
  return {
    person: prospectPerson,
    status: "ready",
    statusMessage: "Public professional research is ready.",
    currentRun: personRun,
    latestRun: personRun,
    observations: [
      observation(
        "person_current_role",
        "current_role",
        "Northstar lists Jane Smith as Chief Technology Officer.",
        "verified",
        [personSource.id],
        "2026-08-25T00:00:00Z",
        "high",
      ),
      observation(
        "person_activity",
        "professional_activity",
        "Jane publicly discussed reliable technology across distributed operations.",
        "verified",
        [personSource.id],
        "2026-07-10T00:00:00Z",
      ),
      observation(
        "person_context",
        "conversation_context",
        "A useful conversation may explore how distributed operations shape technology evaluation.",
        "inferred",
        [personSource.id],
        null,
        "high",
      ),
    ],
    sources: [personSource],
    buyingRoles: [
      {
        id: "role-technical-evaluator",
        role: "technical_evaluator",
        rationale:
          "Her public remit suggests possible evaluation involvement; seller validation is required.",
        trustState: "inferred",
        reviewState: "needs_validation",
        assessmentOrigin: "system_hypothesis",
        sourceIds: [personSource.id],
        reviewedAt: null,
      },
    ],
    contactPoints: [
      {
        id: "contact-point-email",
        pointType: "business_email",
        value: "jane.smith@northstar-facilities.example",
        trustState: "provider_supplied",
        verificationMethod: "provider_reported",
        sourceId: personSource.id,
        observedAt: "2026-08-25T00:00:00Z",
        expiresAt: "2026-09-25T00:00:00Z",
        exportAllowed: true,
        permissionStatus: "not_assessed",
      },
    ],
    changes: [],
    history: [personRun],
    existingContactMatches: [
      {
        id: "contact-jane",
        displayName: "Jane Smith",
        email: "jane.smith@northstar-facilities.example",
        companyId: "company-northstar",
        matchStrength: "strong",
        matchReason: "exact_business_email",
      },
    ],
  };
}

function peopleDiscovery(withPeople: boolean) {
  return {
    companyTargetId: target.id,
    functions: [
      {
        functionKey: "technology",
        label: "Technology",
        whyItMayMatter: "May assess technical fit and implementation impact.",
      },
      {
        functionKey: "finance",
        label: "Finance",
        whyItMayMatter: "May evaluate investment and commercial impact.",
      },
    ],
    people: withPeople ? [prospectPerson] : [],
    gaps: withPeople
      ? [
          {
            role: "security",
            label: "Security",
            message: "No likely security stakeholder has been identified yet.",
          },
        ]
      : [],
    resultLimit: 15,
    message: withPeople
      ? "RevenueOS found 1 person worth understanding. Buying roles remain hypotheses."
      : "Find relevant people from this researched company when you are ready.",
  };
}

async function routeShell(page: Page, enabled = true) {
  await page.route(
    "http://localhost:8000/api/v1/beta/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          featureFlags: { revenueBrain: false, prospect: enabled },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/prospect/availability",
    async (route) => {
      await route.fulfill({
        json: enabled
          ? availability
          : { ...availability, state: "not_in_plan", enabled: false },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/prospect/research/*/people",
    async (route) => route.fulfill({ json: peopleDiscovery(false) }),
  );
  await page.route(
    "http://localhost:8000/api/v1/prospect/target-markets",
    async (route) =>
      route.fulfill({
        json: { items: [], activeLimit: 10, canCreate: true },
      }),
  );
}

test("flagship account research path is sourced, refreshable and explicitly promoted", async ({
  page,
  context,
}) => {
  await routeShell(page);
  let targetState: "processing" | "ready" | "refreshing" | "refreshed" =
    "processing";
  let targetReads = 0;
  let promotionCount = 0;
  const unexpectedMutations: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/api\/v1\/(opportunities|contacts|methodologies|accounts\/.*\/brain)/u.test(
        request.url(),
      )
    ) {
      unexpectedMutations.push(request.url());
    }
  });
  await context.route(
    "https://northstar-facilities.example/**",
    async (route) => {
      await route.fulfill({
        contentType: "text/html",
        body: "<title>Northstar public source</title><h1>Northstar public source</h1>",
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/prospect/companies/search**",
    async (route) => {
      await route.fulfill({
        json: { items: candidates, query: "Northstar", ambiguous: true },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/prospect/research**",
    async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      const method = route.request().method();
      if (path.endsWith("/research") && method === "GET") {
        await route.fulfill({ json: { items: [] } });
        return;
      }
      if (path.endsWith("/research") && method === "POST") {
        expect(route.request().postDataJSON()).toMatchObject({
          candidateId: "northstar-facilities-group",
        });
        await route.fulfill({ status: 202, json: processingBrief() });
        return;
      }
      if (path.endsWith("/refresh") && method === "POST") {
        targetState = "refreshing";
        targetReads = 0;
        await route.fulfill({ status: 202, json: processingBrief() });
        return;
      }
      if (path.endsWith("/promote") && method === "POST") {
        expect(route.request().postDataJSON()).toEqual({
          confirmed: true,
          existingCompanyId: null,
        });
        promotionCount += 1;
        await route.fulfill({
          json: {
            status: "created",
            companyId: "company-northstar",
            companyName: "Northstar Facilities Group",
            researchTargetId: target.id,
            message:
              "The account was added to Sales. No opportunity or contact was created.",
          },
        });
        return;
      }
      if (path.endsWith(`/research/${target.id}`) && method === "GET") {
        targetReads += 1;
        if (targetState === "processing" && targetReads > 2)
          targetState = "ready";
        if (targetState === "refreshing" && targetReads > 2)
          targetState = "refreshed";
        await route.fulfill({
          json:
            targetState === "ready"
              ? readyBrief()
              : targetState === "refreshed"
                ? readyBrief({ refreshed: true })
                : processingBrief(),
        });
        return;
      }
      if (path.endsWith(`/research/${target.id}/people`) && method === "GET") {
        await route.fulfill({ json: peopleDiscovery(false) });
        return;
      }
      await route.fulfill({ status: 404, json: { message: "Not found" } });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/prospect/accounts/company-northstar/research-link",
    async (route) => {
      await route.fulfill({
        json: {
          targetId: target.id,
          companyId: "company-northstar",
          updatedAt: "2026-08-25T00:02:00Z",
          status: "ready",
        },
      });
    },
  );

  await page.goto("/find");
  await expect(
    page.getByRole("heading", { name: "Which company are you looking for?" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Find" })).toBeVisible();
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-find-empty-desktop.png",
      fullPage: true,
    });
  }
  await page
    .getByRole("searchbox", { name: "Search company name or website" })
    .fill("Northstar");
  await page.getByRole("button", { name: "Search companies" }).click();
  await expect(page.getByText(/More than one company matches/i)).toBeVisible();
  await expect(page.getByText("northstar-software.example")).toBeVisible();
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-search-results-desktop.png",
      fullPage: true,
    });
  }
  await page
    .getByRole("article")
    .filter({ hasText: "Northstar Facilities Group" })
    .getByRole("button", { name: "Research company" })
    .click();

  await expect(page).toHaveURL(`/find/${target.id}`);
  await expect(
    page.getByRole("heading", { name: "Researching company…" }),
  ).toBeVisible();
  await expect(
    page.getByText(/You can leave this page and come back/i),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-research-progress-desktop.png",
      fullPage: true,
    });
  }
  await expect(page.getByText("Research ready", { exact: true })).toBeVisible({
    timeout: 8_000,
  });
  for (const label of [
    "Verified",
    "From data provider",
    "RevenueOS inference",
    "Not established",
  ]) {
    await expect(page.getByText(label).first()).toBeVisible();
  }
  await expect(page.getByText(/not customer-confirmed needs/i)).toBeVisible();
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-research-brief-desktop.png",
      fullPage: true,
    });
    await page
      .getByRole("heading", { name: "Sources" })
      .scrollIntoViewIfNeeded();
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-source-disclosure-desktop.png",
    });
  }
  if (process.env.CAPTURE_WO_050_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-050-prospect-company-desktop.png",
      fullPage: true,
    });
  }

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("link", { name: "Open source ↗" }).first().click();
  const sourcePage = await popupPromise;
  await expect(
    sourcePage.getByRole("heading", { name: "Northstar public source" }),
  ).toBeVisible();
  await sourcePage.close();

  await page.getByRole("button", { name: "Refresh research" }).click();
  await expect(page.getByRole("heading", { name: "What changed" })).toBeVisible(
    {
      timeout: 8_000,
    },
  );
  await expect(page.getByText("New", { exact: true })).toBeVisible();
  await expect(page.getByText("Changed", { exact: true })).toBeVisible();
  await expect(
    page.getByText("No longer supported", { exact: true }),
  ).toBeVisible();
  await page.getByText("Research history").click();
  await expect(page.getByText("Previous research")).toBeVisible();

  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-refresh-changes-desktop.png",
      fullPage: true,
    });
  }

  await page.getByRole("button", { name: "Add to Sales" }).click();
  await expect(
    page.getByText(/will not create an Opportunity or Contact/i),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-promotion-confirmation-desktop.png",
    });
  }
  await page.getByRole("button", { name: "Add account" }).click();
  await expect(page.getByRole("link", { name: "Open account" })).toBeVisible();
  await page.getByRole("link", { name: "Open account" }).click();
  await expect(page).toHaveURL("/companies/company-northstar");
  await expect(page.getByText("Separate from customer evidence")).toBeVisible();
  await expect(page.getByRole("link", { name: "View research" })).toBeVisible();
  expect(promotionCount).toBe(1);
  expect(unexpectedMutations).toEqual([]);
});

test("people discovery and person research stay sourced, hypothesis-led and duplicate-safe", async ({
  page,
}) => {
  await routeShell(page);
  const emptyPeopleRoute =
    "http://localhost:8000/api/v1/prospect/research/*/people";
  await page.unroute(emptyPeopleRoute);
  let peopleFound = false;
  let roleReviewed = false;
  let promoted = false;
  const unexpectedMutations: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() !== "GET" &&
      /\/api\/v1\/(opportunities|methodologies|interactions|accounts\/.*\/brain)/u.test(
        request.url(),
      )
    )
      unexpectedMutations.push(request.url());
  });
  await page.route(
    `http://localhost:8000/api/v1/prospect/research/${target.id}`,
    async (route) => route.fulfill({ json: readyBrief() }),
  );
  await page.route(emptyPeopleRoute, async (route) =>
    route.fulfill({ json: peopleDiscovery(peopleFound) }),
  );
  await page.route(
    `http://localhost:8000/api/v1/prospect/research/${target.id}/people/discover`,
    async (route) => {
      peopleFound = true;
      await route.fulfill({ json: peopleDiscovery(true) });
    },
  );
  await page.route(
    `http://localhost:8000/api/v1/prospect/people/${prospectPerson.id}**`,
    async (route) => {
      const url = new URL(route.request().url());
      const method = route.request().method();
      if (url.pathname.endsWith("/promote") && method === "POST") {
        expect(route.request().postDataJSON()).toEqual({
          confirmed: true,
          duplicateAction: "attach_research",
          existingContactId: "contact-jane",
        });
        promoted = true;
        await route.fulfill({
          json: {
            status: "attached",
            contactId: "contact-jane",
            companyId: "company-northstar",
            prospectPersonId: prospectPerson.id,
            message:
              "Public professional research was linked to the existing Contact. No canonical fields were overwritten.",
          },
        });
        return;
      }
      if (url.pathname.includes("/buying-roles/") && method === "PATCH") {
        expect(route.request().postDataJSON()).toEqual({
          role: "technical_evaluator",
          reviewState: "relevant",
        });
        roleReviewed = true;
        await route.fulfill({
          json: {
            ...personResearchBrief().buyingRoles[0],
            reviewState: "relevant",
            assessmentOrigin: "seller_assessed",
            reviewedAt: "2026-08-25T01:00:00Z",
          },
        });
        return;
      }
      await route.fulfill({ json: personResearchBrief() });
    },
  );
  await page.route("http://localhost:8000/api/v1/companies**", async (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "company-northstar",
            organisationId: "org-dev",
            name: "Northstar Facilities Group",
            website: "https://northstar-facilities.example/",
            industry: "Facilities services",
            employeeCount: null,
            status: "prospect",
            ownerUserId: "user-dev",
            createdAt: "2026-08-25T00:00:00Z",
            updatedAt: "2026-08-25T00:00:00Z",
          },
        ],
        page: 1,
        pageSize: 100,
        total: 1,
        pages: 1,
      },
    }),
  );
  await page.route(
    "http://localhost:8000/api/v1/contacts/contact-jane",
    async (route) =>
      route.fulfill({
        json: {
          id: "contact-jane",
          organisationId: "org-dev",
          companyId: "company-northstar",
          firstName: "Jane",
          lastName: "Smith",
          email: "jane.smith@northstar-facilities.example",
          phone: null,
          jobTitle: "Existing reviewed title",
          linkedinUrl: null,
          ownerUserId: "user-dev",
          createdAt: "2026-08-25T00:00:00Z",
          updatedAt: "2026-08-25T00:00:00Z",
        },
      }),
  );
  await page.route(
    "http://localhost:8000/api/v1/prospect/contacts/contact-jane/research-link",
    async (route) =>
      route.fulfill({
        json: {
          contactId: "contact-jane",
          prospectPersonId: prospectPerson.id,
          companyTargetId: target.id,
          updatedAt: "2026-08-25T01:02:00Z",
          label: "Public professional research",
        },
      }),
  );

  await page.goto(`/find/${target.id}`);
  await expect(
    page.getByRole("heading", { name: "People worth understanding" }),
  ).toBeVisible();
  await expect(page.getByText(/not Contacts until/i)).toBeVisible();
  await page.getByRole("button", { name: "Find relevant people" }).click();
  await expect(page.getByText("Jane Smith")).toBeVisible();
  await expect(page.getByText(/No likely security stakeholder/i)).toBeVisible();
  if (process.env.CAPTURE_WO_027_SCREENSHOTS === "1") {
    await page
      .getByRole("heading", { name: "People worth understanding" })
      .scrollIntoViewIfNeeded();
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-027-people-discovery-desktop.png",
      fullPage: true,
    });
  }
  await page.getByRole("link", { name: "View professional research" }).click();
  await expect(page).toHaveURL(
    `/find/${target.id}/people/${prospectPerson.id}`,
  );
  await expect(
    page.getByRole("heading", { name: "Why this person may matter" }),
  ).toBeVisible();
  await expect(page.getByText("Hypothesis — Needs validation")).toBeVisible();
  await expect(
    page.getByText("Permission not assessed", { exact: false }),
  ).toBeVisible();
  await expect(page.locator("img")).toHaveCount(0);
  if (process.env.CAPTURE_WO_027_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-027-person-research-desktop.png",
      fullPage: true,
    });
  }
  if (process.env.CAPTURE_WO_050_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-050-prospect-person-desktop.png",
      fullPage: true,
    });
  }

  await page.getByRole("button", { name: "Mark relevant" }).click();
  await expect(page.getByText("Hypothesis — Relevant")).toBeVisible();
  expect(roleReviewed).toBe(true);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("navigation", { name: "Mobile navigation" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
    ),
  ).toBe(false);
  if (process.env.CAPTURE_WO_027_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-027-person-research-mobile.png",
      fullPage: true,
    });
  }
  if (process.env.CAPTURE_WO_050_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-050-prospect-person-mobile-390.png",
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });

  await page.getByRole("button", { name: "Add to Sales as Contact" }).click();
  await expect(page.getByText("Possible existing Contact")).toBeVisible();
  await expect(
    page.getByText(/will not create an Opportunity, stakeholder role/i),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_027_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-027-contact-promotion-review-desktop.png",
    });
  }
  await page.getByRole("button", { name: "Attach research" }).click();
  await expect(page.getByRole("link", { name: "Open Contact" })).toBeVisible();
  expect(promoted).toBe(true);
  expect(unexpectedMutations).toEqual([]);
  await page.getByRole("link", { name: "Open Contact" }).click();
  await expect(page).toHaveURL("/contacts/contact-jane");
  await expect(
    page.getByRole("heading", { name: "Public professional research" }),
  ).toBeVisible();
  await expect(
    page.getByText(/separate from customer evidence/i),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_027_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-027-promoted-contact-desktop.png",
      fullPage: true,
    });
  }
});

test("exact-domain existing Account is attached without a duplicate", async ({
  page,
}) => {
  await routeShell(page);
  let promoted = false;
  await page.route(
    `http://localhost:8000/api/v1/prospect/research/${target.id}`,
    async (route) => {
      await route.fulfill({ json: readyBrief({ existing: true }) });
    },
  );
  await page.route(
    `http://localhost:8000/api/v1/prospect/research/${target.id}/promote`,
    async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        confirmed: true,
        existingCompanyId: "company-existing",
      });
      promoted = true;
      await route.fulfill({
        json: {
          status: "attached",
          companyId: "company-existing",
          companyName: "Northstar Facilities Group",
          researchTargetId: target.id,
          message: "Public research was attached to the existing account.",
        },
      });
    },
  );
  await page.goto(`/find/${target.id}`);
  await page.getByRole("button", { name: "Add to Sales" }).click();
  await expect(
    page.getByText("This company is already in RevenueOS"),
  ).toBeVisible();
  await expect(
    page.getByText(/No duplicate Account will be created/i),
  ).toBeVisible();
  await page.getByRole("button", { name: "Attach research" }).click();
  await expect(
    page.getByRole("link", { name: "Open account" }),
  ).toHaveAttribute("href", "/companies/company-existing");
  expect(promoted).toBe(true);
});

test("partial research retains supported findings", async ({ page }) => {
  await routeShell(page);
  await page.route(
    `http://localhost:8000/api/v1/prospect/research/${target.id}`,
    async (route) => route.fulfill({ json: readyBrief({ partial: true }) }),
  );
  await page.goto(`/find/${target.id}`);
  await expect(
    page.getByText("Research incomplete", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/partial brief, but some sources were unavailable/i),
  ).toBeVisible();
  await expect(
    page.getByText(/manages facilities operations across 18/i),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-partial-research-desktop.png",
      fullPage: true,
    });
  }
});

test("failed research provides one clear retry path", async ({ page }) => {
  await routeShell(page);
  await page.route(
    `http://localhost:8000/api/v1/prospect/research/${target.id}`,
    async (route) => route.fulfill({ json: failedBrief() }),
  );
  await page.goto(`/find/${target.id}`);
  await expect(
    page.getByRole("heading", { name: "Couldn’t complete research" }).last(),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Refresh research" }),
  ).toHaveCount(0);
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-failed-research-desktop.png",
      fullPage: true,
    });
  }
});

test("non-entitled workspace gets a restrained explanation and no research call", async ({
  page,
}) => {
  await routeShell(page, false);
  const researchCalls: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/prospect/research"))
      researchCalls.push(request.url());
  });
  await page.goto("/find");
  await expect(
    page.getByText(/Prospect is not available in this workspace/i),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "View Accounts" })).toBeVisible();
  await expect(page.getByText(/buy|price|upgrade/i)).toHaveCount(0);
  expect(researchCalls).toEqual([]);
});

test("Find and the concise brief remain usable on mobile without changing mobile navigation", async ({
  page,
}) => {
  await routeShell(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route(
    "http://localhost:8000/api/v1/prospect/research",
    async (route) => route.fulfill({ json: { items: [] } }),
  );
  await page.route(
    `http://localhost:8000/api/v1/prospect/research/${target.id}`,
    async (route) => route.fulfill({ json: readyBrief() }),
  );
  await page.goto("/find");
  await expect(page.getByRole("searchbox")).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Mobile navigation" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Mobile navigation" })
      .getByRole("link", { name: "Find" }),
  ).toHaveCount(0);
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-find-mobile.png",
      fullPage: true,
    });
  }
  await page.goto(`/find/${target.id}`);
  await expect(
    page.getByRole("button", { name: "Add to Sales" }),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_026_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-026-research-brief-mobile.png",
      fullPage: true,
    });
  }
  if (process.env.CAPTURE_WO_050_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-050-prospect-company-mobile-390.png",
      fullPage: true,
    });
  }
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
});
