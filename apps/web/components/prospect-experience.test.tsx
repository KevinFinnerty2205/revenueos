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
import {
  ContactPublicProfessionalResearch,
  ProspectPeopleSection,
  ProspectPersonResearchView,
} from "@/components/prospect-people";
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

const providerReadiness = {
  candidateProvider: "apollo",
  adapterState: "UNCONFIGURED",
  productionCapable: true,
  productionActive: false,
  externalExecutionEnabled: false,
  credentialConfigured: false,
  productionCreditPricesAvailable: false,
  productionCreditPacksAvailable: false,
  autoTopUp: false,
  recentProfessionalPostsAvailable: false,
  phoneRevealEnabled: false,
  blockers: [
    "Provider credentials are not configured.",
    "Product-use licensing is not approved.",
  ],
  message: "The live Prospect adapter is installed but cannot execute yet.",
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

const person = {
  id: "person-1",
  companyTargetId: "target-1",
  displayName: "Jane Smith",
  currentRole: "Chief Technology Officer",
  currentCompany: "Northstar Facilities Group",
  publicProfessionalLocation: "Sydney, Australia",
  publicProfileUrl:
    "https://northstar-facilities.example/leadership/jane-smith",
  relevantFunction: "technology",
  whyMayMatter:
    "Her public remit suggests she may help evaluate operational technology change.",
  providerAttribution: "RevenueOS synthetic research data",
  identityState: "supported",
  employmentState: "current",
  researchStatus: "ready",
  promotedContactId: null,
  promotedAt: null,
  createdAt: "2026-08-25T01:00:00Z",
  updatedAt: "2026-08-25T01:02:00Z",
};

const personSources = [
  {
    id: "person-source-1",
    sourceType: "company_leadership",
    url: "https://northstar-facilities.example/leadership/jane-smith",
    canonicalUrl: "https://northstar-facilities.example/leadership/jane-smith",
    domain: "northstar-facilities.example",
    title: "Jane Smith leadership profile",
    publisher: "Northstar Facilities Group",
    publishedAt: null,
    retrievedAt: "2026-08-25T01:02:00Z",
    authorityClass: "official_public",
  },
];

function personBrief(overrides: Record<string, object> = {}) {
  const run = {
    id: "person-run-1",
    status: "completed",
    refreshOfRunId: null,
    createdAt: "2026-08-25T01:00:00Z",
    startedAt: "2026-08-25T01:01:00Z",
    completedAt: "2026-08-25T01:02:00Z",
    sourceCount: 1,
    observationCount: 3,
    errorCode: null,
  };
  return {
    person,
    status: "ready",
    statusMessage: "Public professional research is ready.",
    currentRun: run,
    latestRun: run,
    observations: [
      {
        id: "person-observation-1",
        observationKey: "current_role",
        category: "current_role",
        statement: "Northstar lists Jane Smith as Chief Technology Officer.",
        trustState: "verified",
        relevance: "high",
        observedAt: "2026-08-25T00:00:00Z",
        freshness: "time_sensitive",
        sourceIds: ["person-source-1"],
      },
      {
        id: "person-observation-2",
        observationKey: "professional_activity",
        category: "professional_activity",
        statement:
          "Jane publicly discussed reliable technology across distributed operations.",
        trustState: "verified",
        relevance: "normal",
        observedAt: "2026-07-10T00:00:00Z",
        freshness: "time_sensitive",
        sourceIds: ["person-source-1"],
      },
      {
        id: "person-observation-3",
        observationKey: "conversation_context",
        category: "conversation_context",
        statement:
          "A useful conversation may explore how distributed operations shape technology evaluation.",
        trustState: "inferred",
        relevance: "high",
        observedAt: null,
        freshness: "time_sensitive",
        sourceIds: ["person-source-1"],
      },
    ],
    sources: personSources,
    buyingRoles: [
      {
        id: "role-1",
        role: "technical_evaluator",
        rationale:
          "Her public technology remit suggests possible evaluation involvement; seller validation is required.",
        trustState: "inferred",
        reviewState: "needs_validation",
        assessmentOrigin: "system_hypothesis",
        sourceIds: ["person-source-1"],
        reviewedAt: null,
      },
    ],
    contactPoints: [
      {
        id: "point-1",
        pointType: "business_email",
        value: "jane.smith@northstar-facilities.example",
        trustState: "provider_supplied",
        verificationMethod: "provider_reported",
        sourceId: "person-source-1",
        observedAt: "2026-08-25T00:00:00Z",
        expiresAt: "2026-09-25T00:00:00Z",
        exportAllowed: true,
        permissionStatus: "not_assessed",
      },
    ],
    changes: [],
    history: [run],
    existingContactMatches: [
      {
        id: "contact-1",
        displayName: "Jane Smith",
        email: "jane.smith@northstar-facilities.example",
        companyId: "company-1",
        matchStrength: "strong",
        matchReason: "exact_business_email",
      },
    ],
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
      if (url.endsWith("/prospect/target-markets"))
        return jsonResponse({ items: [], activeLimit: 10, canCreate: true });
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
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/research/target-1/people"))
        return jsonResponse({
          companyTargetId: "target-1",
          functions: [],
          people: [],
          gaps: [],
          resultLimit: 15,
          message: "Find relevant people when you are ready.",
        });
      if (url.endsWith("/research/target-1/refresh"))
        return jsonResponse(refreshed, 202);
      if (url.endsWith("/research/target-1/promote"))
        return jsonResponse({
          status: "created",
          companyId: "company-1",
          companyName: "Northstar Facilities Group",
          researchTargetId: "target-1",
          message:
            "The account was added to Sales. No opportunity or contact was created.",
        });
      if (url.endsWith("/research/target-1") && !init?.method)
        return jsonResponse(researchBrief());
      throw new Error(`Unexpected request: ${url}`);
    });
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

  it.each([
    [
      "unknown",
      "Reconciling provider outcome",
      /Reserved Credits remain held/i,
    ],
    [
      "no_result",
      "No reliable results",
      /no research was promoted into Sales/i,
    ],
  ] as const)(
    "renders the %s provider outcome safely",
    async (status, heading, message) => {
      const ready = researchBrief();
      const latestRun = { ...ready.latestRun, status, providerOutcome: status };
      const body = {
        ...ready,
        status,
        statusMessage:
          status === "unknown"
            ? "The provider outcome is unknown."
            : "No reliable result was returned.",
        currentRun: null,
        latestRun,
        observations: [],
        sources: [],
        history: [latestRun],
      };
      vi.stubGlobal(
        "fetch",
        vi.fn((input: RequestInfo | URL) =>
          String(input).endsWith("/research/target-1/people")
            ? jsonResponse({
                companyTargetId: "target-1",
                functions: [],
                people: [],
                gaps: [],
                resultLimit: 15,
                message: "No people research available.",
              })
            : jsonResponse(body),
        ),
      );

      render(<ProspectResearchBriefView targetId="target-1" />);

      expect(
        await screen.findByRole("heading", { name: heading }),
      ).toBeVisible();
      expect(screen.getByText(message)).toBeVisible();
      expect(
        screen.queryByRole("button", { name: "Add to Sales" }),
      ).not.toBeInTheDocument();
      if (status === "unknown") {
        expect(
          screen.queryByRole("button", { name: "Refresh research" }),
        ).not.toBeInTheDocument();
      }
    },
  );

  it("discovers a bounded company-scoped set of people without social-profile imagery", async () => {
    const empty = {
      companyTargetId: "target-1",
      functions: [
        {
          functionKey: "technology",
          label: "Technology",
          whyItMayMatter: "May assess technical fit and implementation impact.",
        },
      ],
      people: [],
      gaps: [],
      resultLimit: 15,
      message: "Find relevant people when you are ready.",
    };
    const discovered = {
      ...empty,
      people: [person],
      gaps: [
        {
          role: "security",
          label: "Security",
          message: "No likely security stakeholder has been identified yet.",
        },
      ],
      message:
        "RevenueOS found 1 person worth understanding. Buying roles remain hypotheses.",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === "POST" ? jsonResponse(discovered) : jsonResponse(empty),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(<ProspectPeopleSection targetId="target-1" />);

    expect(
      await screen.findByText(/not Contacts until you explicitly add them/i),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Find relevant people" }),
    );
    expect(await screen.findByText("Jane Smith")).toBeVisible();
    expect(screen.getByText(/No likely security stakeholder/i)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "View professional research" }),
    ).toHaveAttribute("href", "/find/target-1/people/person-1");
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "POST" });
  });

  it("renders sourced person intelligence, validates hypotheses and reviews duplicates before promotion", async () => {
    const reviewedRole = {
      ...personBrief().buyingRoles[0],
      reviewState: "relevant",
      assessmentOrigin: "seller_assessed",
      reviewedAt: "2026-08-25T02:00:00Z",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/buying-roles/role-1") && init?.method === "PATCH")
        return jsonResponse(reviewedRole);
      if (url.endsWith("/people/person-1/promote"))
        return jsonResponse({
          status: "attached",
          contactId: "contact-1",
          companyId: "company-1",
          prospectPersonId: "person-1",
          message:
            "Public professional research was linked to the existing Contact. No canonical fields were overwritten.",
        });
      if (url.endsWith("/people/person-1")) return jsonResponse(personBrief());
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(
      <ProspectPersonResearchView personId="person-1" />,
    );

    expect(
      await screen.findByRole("heading", { name: "Jane Smith" }),
    ).toBeVisible();
    expect(screen.getByText("Hypothesis — Needs validation")).toBeVisible();
    expect(
      screen.getByText("Permission not assessed", { exact: false }),
    ).toBeVisible();
    expect(
      screen.getByText(/do not change Stakeholder Intelligence/i),
    ).toBeVisible();
    expect(container.querySelector("img")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Mark relevant" }));
    expect(await screen.findByText("Hypothesis — Relevant")).toBeVisible();

    fireEvent.click(
      screen.getByRole("button", { name: "Add to Sales as Contact" }),
    );
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Possible existing Contact")).toBeVisible();
    expect(
      within(dialog).getByText(
        /will not create an Opportunity, stakeholder role/i,
      ),
    ).toBeVisible();
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Attach research" }),
    );
    expect(
      await screen.findByRole("link", { name: "Open Contact" }),
    ).toHaveAttribute("href", "/contacts/contact-1");
    const promotionBody = JSON.parse(
      String(fetchMock.mock.calls.at(-1)?.[1]?.body),
    );
    expect(promotionBody).toMatchObject({
      confirmed: true,
      duplicateAction: "attach_research",
      existingContactId: "contact-1",
    });
  });

  it("keeps promoted Contact research visibly separate from customer truth", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        jsonResponse({
          contactId: "contact-1",
          prospectPersonId: "person-1",
          companyTargetId: "target-1",
          updatedAt: "2026-08-25T01:02:00Z",
          label: "Public professional research",
        }),
      ),
    );
    render(<ContactPublicProfessionalResearch contactId="contact-1" />);
    expect(
      await screen.findByRole("heading", {
        name: "Public professional research",
      }),
    ).toBeVisible();
    expect(screen.getByText(/separate from customer evidence/i)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "View public research" }),
    ).toHaveAttribute("href", "/find/target-1/people/person-1");
  });

  it("shows a departed-role warning and unknown contact state without preserving a buying-role claim", async () => {
    const cautiousBrief = personBrief();
    cautiousBrief.person = {
      ...cautiousBrief.person,
      currentRole: "Former Chief Technology Officer",
      employmentState: "no_longer_current",
      whyMayMatter:
        "Jane's role may have changed; her former remit is historical professional context only.",
    };
    cautiousBrief.status = "partial";
    cautiousBrief.statusMessage =
      "Role may have changed. Newer information suggests this person is no longer current.";
    cautiousBrief.buyingRoles = [];
    cautiousBrief.contactPoints = [];
    cautiousBrief.existingContactMatches = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => jsonResponse(cautiousBrief)),
    );

    render(<ProspectPersonResearchView personId="person-1" />);

    expect(await screen.findByText("Role may have changed")).toBeVisible();
    expect(
      screen.getByText("No supported buying-role hypothesis was established."),
    ).toBeVisible();
    expect(screen.getByText(/did not guess an email address/i)).toBeVisible();
  });

  it("lets an administrator toggle the server-authoritative module entitlement", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => jsonResponse(availability))
      .mockImplementationOnce(() => jsonResponse(providerReadiness))
      .mockImplementationOnce(() =>
        jsonResponse({ ...availability, state: "not_in_plan", enabled: false }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ProspectModuleSettings />);
    const toggle = await screen.findByRole("switch", { name: "Enabled" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(await screen.findByText("Live research readiness")).toBeVisible();
    expect(screen.getByText("Not active")).toBeVisible();
    fireEvent.click(toggle);
    expect(
      await screen.findByRole("switch", { name: "Disabled" }),
    ).toHaveAttribute("aria-checked", "false");
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({ method: "PATCH" });
  });
});
