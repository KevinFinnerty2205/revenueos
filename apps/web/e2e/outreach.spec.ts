import { expect, test } from "@playwright/test";

const contactId = "contact-northstar-jane";
const outreachId = "outreach-northstar-jane";
const actionId = "action-northstar-jane";

async function capture(
  page: import("@playwright/test").Page,
  name: string,
  fullPage = true,
) {
  if (process.env.WO029_SCREENSHOTS !== "1") return;
  await page.screenshot({
    path: `../../docs/07-sprints/images/wo-029/${name}.png`,
    fullPage,
  });
}

const contactability = {
  state: "allowed",
  allowed: true,
  reason:
    "Allowed under the configured organisation policy. Address trust does not itself establish permission.",
  trustState: "provider_supplied",
  permissionAssessedSeparately: true,
};

function workspace(
  overrides: Record<string, unknown> = {},
  history: Array<Record<string, unknown>> = [],
) {
  return {
    availability: {
      moduleKey: "engage",
      state: "available",
      enabled: true,
      canManage: true,
      message: "RevenueOS Engage is available for this organisation.",
    },
    contactId,
    contactName: "Jane Smith",
    companyId: "company-northstar",
    companyName: "Northstar Facilities Group",
    jobTitle: "Chief Information Officer",
    email: "jane.smith@northstar-facilities.example",
    emailTrust: "provider_supplied",
    permissionStatus: "assessed_by_organisation_policy",
    contactability,
    policyConfigured: true,
    productionMailboxAvailable: false,
    simulationAvailable: true,
    history,
    ...overrides,
  };
}

function outreach(
  overrides: Record<string, unknown> = {},
  versionOverrides: Record<string, unknown> = {},
) {
  return {
    id: outreachId,
    actionId,
    contactId,
    purpose: "request_meeting",
    state: "draft",
    currentVersion: 1,
    approvedVersion: null,
    version: {
      id: "version-northstar-1",
      version: 1,
      subject: "Multi-site growth at Northstar Facilities Group",
      body: "Hi Jane,\n\nNorthstar's expansion and your technology consolidation work prompted me to get in touch. We help multi-site teams manage access consistently across locations.\n\nWould a short conversation next week be useful?\n\nRegards,\nAlex",
      senderName: "Alex Morgan",
      senderEmail: "alex@example.test",
      recipientName: "Jane Smith",
      recipientEmail: "jane.smith@northstar-facilities.example",
      recipientTrust: "provider_supplied",
      creationType: "generated",
      composerVersion: "outreach_deterministic_v1",
      personalizationUsed: true,
      sources: [
        {
          id: "source-expansion",
          sourceType: "prospect_observation",
          sourceId: "observation-expansion",
          label:
            "Northstar announced expansion into three additional Australian locations.",
          trustState: "verified",
          publisher: "Northstar Newsroom",
          publishedAt: "2026-05-14T00:00:00Z",
          url: "https://northstar-facilities.example/news/expansion",
        },
        {
          id: "source-technology",
          sourceType: "prospect_person_observation",
          sourceId: "observation-technology",
          label:
            "Jane described consolidating technology across distributed operations.",
          trustState: "verified",
          publisher: "Facilities Technology Forum",
          publishedAt: "2026-06-20T00:00:00Z",
          url: "https://northstar-facilities.example/news/technology-forum",
        },
        {
          id: "source-offering",
          sourceType: "approved_seller_context",
          sourceId: "organisation-1",
          label: "Approved seller offering: Multi-site Access Management",
          trustState: "approved",
          publisher: null,
          publishedAt: null,
          url: null,
        },
      ],
      warnings: [],
      createdAt: "2026-08-26T01:00:00Z",
      ...versionOverrides,
    },
    contactability,
    relationshipWarning: null,
    execution: null,
    createdAt: "2026-08-26T01:00:00Z",
    updatedAt: "2026-08-26T01:00:00Z",
    ...overrides,
  };
}

const executionOptions = {
  items: [
    {
      connectionId: "connection-mock-email",
      connectorKey: "mock_email",
      connectorDisplayName: "Mock Email",
      capability: "send_email",
      riskClass: "external_customer_facing",
      executionMode: "simulation",
      simulationOnly: true,
    },
  ],
  total: 1,
};

function execution(status: "queued" | "simulated_success") {
  return {
    id: "execution-northstar",
    actionProposalId: actionId,
    actionVersion: 2,
    connectionId: "connection-mock-email",
    connectorKey: "mock_email",
    connectorDisplayName: "Mock Email",
    capability: "send_email",
    riskClass: "external_customer_facing",
    executionStatus: status,
    executionMode: "simulation",
    simulationOnly: true,
    attemptCount: status === "queued" ? 0 : 1,
    providerReference: null,
    safeMessage:
      status === "queued"
        ? "The email simulation is queued."
        : "The email simulation completed successfully.",
    requestedAt: "2026-08-26T01:05:00Z",
    confirmedAt: "2026-08-26T01:05:00Z",
    startedAt: status === "queued" ? null : "2026-08-26T01:05:01Z",
    completedAt: status === "queued" ? null : "2026-08-26T01:05:01Z",
    createdAt: "2026-08-26T01:05:00Z",
    updatedAt: "2026-08-26T01:05:01Z",
  };
}

test("creates, explains, edits, approves and simulates flagship outreach", async ({
  page,
}) => {
  let version = 1;
  let approved = false;
  let completed = false;
  let draftBody = "";

  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === `/api/v1/engage/contacts/${contactId}`) {
      await route.fulfill({
        json: workspace(
          {},
          completed
            ? [
                {
                  id: outreachId,
                  subject: "Northstar's next phase",
                  status: "simulated_success",
                  simulationOnly: true,
                  createdAt: "2026-08-26T01:00:00Z",
                },
              ]
            : [],
        ),
      });
      return;
    }
    if (
      path === `/api/v1/engage/contacts/${contactId}/outreach` &&
      request.method() === "POST"
    ) {
      expect(request.postDataJSON()).toEqual({ purpose: "request_meeting" });
      await route.fulfill({ status: 201, json: outreach() });
      return;
    }
    if (
      path === `/api/v1/engage/outreach/${outreachId}` &&
      request.method() === "PATCH"
    ) {
      const payload = request.postDataJSON() as {
        expectedVersion: number;
        subject: string;
        body: string;
      };
      expect(payload.expectedVersion).toBe(1);
      expect(payload.body).toContain("operational consistency");
      version = 2;
      draftBody = payload.body;
      await route.fulfill({
        json: outreach(
          { currentVersion: 2 },
          {
            id: "version-northstar-2",
            version: 2,
            subject: payload.subject,
            body: payload.body,
            creationType: "user_edited",
          },
        ),
      });
      return;
    }
    if (path === `/api/v1/engage/outreach/${outreachId}/approve`) {
      expect(request.postDataJSON()).toEqual({ expectedVersion: 2 });
      approved = true;
      await route.fulfill({
        json: outreach(
          { state: "approved", currentVersion: 2, approvedVersion: 2 },
          {
            id: "version-northstar-2",
            version: 2,
            subject: "Northstar's next phase",
            body: draftBody,
            creationType: "user_edited",
          },
        ),
      });
      return;
    }
    if (path === `/api/v1/actions/${actionId}/execution-options`) {
      await route.fulfill({ json: executionOptions });
      return;
    }
    if (path === `/api/v1/engage/outreach/${outreachId}/execution-preview`) {
      expect(approved).toBe(true);
      await route.fulfill({
        json: {
          id: "preview-northstar",
          actionProposalId: actionId,
          actionVersion: 2,
          connectionId: "connection-mock-email",
          connectorKey: "mock_email",
          connectorDisplayName: "Mock Email",
          capability: "send_email",
          riskClass: "external_customer_facing",
          executionMode: "simulation",
          simulationOnly: true,
          readiness: "ready",
          summary: "Review the exact email before simulation.",
          confirmationLabel: "Run email simulation",
          previewFingerprint: "a".repeat(64),
          content: {
            kind: "email",
            senderName: "Alex Morgan",
            senderEmail: "alex@example.test",
            recipientName: "Jane Smith",
            recipient: "jane.smith@northstar-facilities.example",
            subject: "Northstar's next phase",
            body: draftBody,
            action: "send_email",
          },
          expiresAt: "2026-08-26T01:15:00Z",
          createdAt: "2026-08-26T01:05:00Z",
        },
      });
      return;
    }
    if (path === `/api/v1/engage/outreach/${outreachId}/send`) {
      await route.fulfill({ status: 202, json: execution("queued") });
      return;
    }
    if (path === "/api/v1/executions/execution-northstar") {
      completed = true;
      await route.fulfill({ json: execution("simulated_success") });
      return;
    }
    if (
      path === `/api/v1/engage/outreach/${outreachId}` &&
      request.method() === "GET"
    ) {
      await route.fulfill({
        json: outreach(
          {
            state: "simulated_success",
            currentVersion: version,
            approvedVersion: version,
            execution: execution("simulated_success"),
          },
          {
            id: "version-northstar-2",
            version,
            subject: "Northstar's next phase",
            body: draftBody,
            creationType: "user_edited",
          },
        ),
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { message: `Unhandled ${path}` },
    });
  });

  await page.goto(`/contacts/${contactId}`);
  await expect(page.getByRole("heading", { name: "Jane Smith" })).toBeVisible();
  await expect(page.getByText("Provider Supplied")).toBeVisible();
  await capture(page, "create-outreach-desktop");
  await page.getByLabel("Purpose").selectOption("request_meeting");
  await page.getByRole("button", { name: "Create outreach draft" }).click();
  await expect(
    page.getByRole("heading", { name: "Review personalised email" }),
  ).toBeVisible();
  await expect(page.getByLabel("Email body")).toContainText(
    "technology consolidation",
  );
  await page.getByText("Why this message?").click();
  await expect(page.getByText(/expansion into three/u)).toBeVisible();
  await expect(page.getByText(/consolidating technology/u)).toBeVisible();
  await expect(page.getByText(/Multi-site Access Management/u)).toBeVisible();
  await expect(
    page.getByText(/religion|health|family|personality/u),
  ).toHaveCount(0);
  await capture(page, "draft-sources-desktop");
  if (process.env.WO029_SCREENSHOTS === "1") {
    await page.setViewportSize({ width: 390, height: 844 });
    await page
      .getByRole("heading", { name: "Review personalised email" })
      .evaluate((element) => element.scrollIntoView({ block: "start" }));
    await capture(page, "draft-mobile", false);
    await page
      .getByText("Why this message?")
      .evaluate((element) => element.scrollIntoView({ block: "start" }));
    await capture(page, "draft-sources-mobile", false);
    await page.setViewportSize({ width: 1280, height: 720 });
  }

  await page.getByLabel("Subject").fill("Northstar's next phase");
  await page
    .getByLabel("Email body")
    .fill(
      "Hi Jane,\n\nNorthstar's expansion and your technology consolidation work prompted me to get in touch. We help multi-site teams improve operational consistency.\n\nWould a short conversation next week be useful?\n\nRegards,\nAlex",
    );
  await page.getByRole("button", { name: "Save as new version" }).click();
  await expect(page.getByText(/Version 2/u)).toBeVisible();
  await page.getByRole("button", { name: "Approve current version" }).click();
  await expect(
    page.locator("span").getByText("Approved", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Review before send" }).click();

  await expect(
    page.getByRole("heading", { name: "Review exact email" }),
  ).toBeVisible();
  await expect(page.getByText("Simulation only")).toBeVisible();
  await expect(page.getByText("Alex Morgan <alex@example.test>")).toBeVisible();
  await expect(
    page.getByText("Jane Smith <jane.smith@northstar-facilities.example>"),
  ).toBeVisible();
  await expect(page.getByText("Northstar's next phase")).toBeVisible();
  await capture(page, "exact-preview-desktop");
  if (process.env.WO029_SCREENSHOTS === "1") {
    await page.setViewportSize({ width: 390, height: 844 });
    await page
      .getByLabel("Review exact email")
      .evaluate((element) => element.scrollIntoView({ block: "start" }));
    await capture(page, "exact-preview-mobile", false);
    await page.setViewportSize({ width: 1280, height: 720 });
  }
  await page.getByRole("button", { name: "Run email simulation" }).click();
  await expect(page.getByText("Queued", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Refresh status" }).click();
  await expect(
    page.getByText("Simulated Success", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByLabel("Review exact email")
      .getByText("The email simulation completed successfully."),
  ).toBeVisible();
  await expect(page.getByLabel("Outreach history")).toContainText(
    "Northstar's next phase",
  );
  await capture(page, "simulated-success-desktop");
});

test("uses transparent value-based copy when no reliable hook exists", async ({
  page,
}) => {
  const noHook = outreach(
    {},
    {
      subject: "A practical introduction for Northstar Facilities Group",
      body: "Hi Jane,\n\nI work with multi-site teams on consistent access management. Would a short introduction be useful?\n\nRegards,\nAlex",
      personalizationUsed: false,
      sources: [
        {
          id: "source-offering-only",
          sourceType: "approved_seller_context",
          sourceId: "organisation-1",
          label: "Approved seller offering: Multi-site Access Management",
          trustState: "approved",
          publisher: null,
          publishedAt: null,
          url: null,
        },
      ],
      warnings: [
        "No reliable professional research hook was available; no hook was invented.",
      ],
    },
  );
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === `/api/v1/engage/contacts/${contactId}`) {
      await route.fulfill({ json: workspace() });
      return;
    }
    if (path === `/api/v1/engage/contacts/${contactId}/outreach`) {
      await route.fulfill({ status: 201, json: noHook });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { message: `Unhandled ${path}` },
    });
  });

  await page.goto(`/contacts/${contactId}`);
  await page.getByRole("button", { name: "Create outreach draft" }).click();
  await expect(page.getByLabel("Email body")).toContainText(
    "I work with multi-site teams",
  );
  await page.getByText("Why this message?").click();
  await expect(
    page.getByText(/No reliable personalised hook was available/u),
  ).toBeVisible();
  await expect(page.getByText(/no hook was invented/u)).toBeVisible();
  await capture(page, "no-personalisation-desktop");
});

test("suppression blocks approval and the mobile workflow remains usable", async ({
  page,
}) => {
  let suppressed = false;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === `/api/v1/engage/contacts/${contactId}`) {
      await route.fulfill({
        json: workspace(
          suppressed
            ? {
                contactability: {
                  ...contactability,
                  state: "suppressed",
                  allowed: false,
                  reason: "This Contact was marked Do not contact.",
                },
              }
            : {},
        ),
      });
      return;
    }
    if (path === `/api/v1/engage/contacts/${contactId}/suppression`) {
      suppressed = true;
      await route.fulfill({
        status: 201,
        json: {
          id: "suppression-northstar",
          reason: "manual_do_not_contact",
          active: true,
          createdAt: "2026-08-26T01:00:00Z",
        },
      });
      return;
    }
    if (path === `/api/v1/engage/contacts/${contactId}/outreach`) {
      await route.fulfill({ status: 201, json: outreach() });
      return;
    }
    if (path === `/api/v1/engage/outreach/${outreachId}`) {
      await route.fulfill({
        json: outreach({
          contactability: {
            ...contactability,
            state: "suppressed",
            allowed: false,
            reason: "This Contact was marked Do not contact.",
          },
        }),
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { message: `Unhandled ${path}` },
    });
  });

  await page.goto(`/contacts/${contactId}`);
  await expect(page.getByRole("heading", { name: "Jane Smith" })).toBeVisible();
  await page.getByRole("button", { name: "Create outreach draft" }).click();
  await expect(
    page.getByRole("heading", { name: "Review personalised email" }),
  ).toBeVisible();
  await page.getByText("Why this message?").click();
  await expect(page.getByText(/expansion into three/u)).toBeVisible();
  await page.getByRole("button", { name: "Mark Do not contact" }).click();
  await expect(page.getByText("Suppressed", { exact: true })).toBeVisible();
  await expect(
    page.getByText("This Contact was marked Do not contact."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve current version" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Mark Do not contact" }),
  ).toBeDisabled();
  await page
    .getByRole("heading", { name: "Jane Smith" })
    .scrollIntoViewIfNeeded();
  await capture(page, "suppressed-mobile", false);
  if (process.env.WO029_SCREENSHOTS === "1") {
    await page.setViewportSize({ width: 1280, height: 720 });
    await capture(page, "suppressed-desktop");
  }
});

test("shows no-email and existing-relationship safeguards", async ({
  page,
}) => {
  let scenario: "no_email" | "relationship" = "no_email";
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === `/api/v1/engage/contacts/${contactId}`) {
      await route.fulfill({
        json:
          scenario === "no_email"
            ? workspace({
                email: null,
                emailTrust: "unknown",
                contactability: {
                  ...contactability,
                  state: "no_business_email",
                  allowed: false,
                  reason: "This Contact has no business email address.",
                  trustState: "unknown",
                },
              })
            : workspace(),
      });
      return;
    }
    if (
      scenario === "relationship" &&
      path === `/api/v1/engage/contacts/${contactId}/outreach`
    ) {
      await route.fulfill({
        status: 201,
        json: outreach({
          relationshipWarning:
            "Recent customer interaction exists. Confirm this should be a follow-up rather than a new introduction.",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: { message: `Unhandled ${path}` },
    });
  });

  await page.goto(`/contacts/${contactId}`);
  await expect(
    page.getByText("This Contact has no business email address."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create outreach draft" }),
  ).toBeDisabled();
  await capture(page, "no-email-desktop");

  scenario = "relationship";
  await page.reload();
  await page.getByRole("button", { name: "Create outreach draft" }).click();
  await expect(
    page.getByText(/Recent customer interaction exists/u),
  ).toBeVisible();
  await capture(page, "existing-relationship-desktop");
});

test("keeps Engage administration bounded and explicit", async ({ page }) => {
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/me") {
      await route.fulfill({
        json: {
          user: {
            id: "user-1",
            externalAuthId: "user_dev_001",
            displayName: "Alex Morgan",
            email: "alex@example.test",
          },
          organisation: {
            id: "organisation-1",
            name: "Example Revenue Team",
            slug: "example-revenue-team",
          },
          role: "admin",
          authMode: "mock",
          requestId: "request-wo-029-settings",
        },
      });
      return;
    }
    if (path === "/api/v1/engage/availability") {
      await route.fulfill({
        json: {
          moduleKey: "engage",
          state: "available",
          enabled: true,
          canManage: true,
          message: "RevenueOS Engage is available for this organisation.",
        },
      });
      return;
    }
    if (path === "/api/v1/engage/policy") {
      await route.fulfill({
        json: {
          configured: true,
          outboundEnabled: true,
          providerSuppliedEmailAllowed: true,
          cooldownHours: 72,
          maxDailySendsUser: 25,
          maxDailySendsOrg: 100,
          requireOptOutMechanism: false,
          offeringName: "Multi-site Access Management",
          valueProposition: "Coordinate secure access across locations.",
          approvedCta: "Would a short conversation next week be useful?",
          canManage: true,
          complianceNotice:
            "RevenueOS provides configurable product controls, not legal advice.",
        },
      });
      return;
    }
    await route.fulfill({
      status: 403,
      json: { code: "forbidden", message: "Synthetic screenshot route." },
    });
  });

  await page.goto("/settings");
  const engage = page.locator("section", {
    has: page.getByRole("heading", { name: "RevenueOS Engage" }),
  });
  await expect(engage.getByLabel("Approved offering")).toHaveValue(
    "Multi-site Access Management",
  );
  await expect(engage.getByLabel("Daily limit per sender")).toHaveValue("25");
  await expect(
    engage.getByText(
      /Production Gmail and Microsoft mailbox adapters are not enabled/u,
    ),
  ).toBeVisible();
  if (process.env.WO029_SCREENSHOTS === "1") {
    await engage.screenshot({
      path: "../../docs/07-sprints/images/wo-029/engage-policy-desktop.png",
    });
  }
});
