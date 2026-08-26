import { expect, test } from "@playwright/test";

const campaignId = "campaign-australian-cio";
const enrollmentId = "enrollment-jane";
const outreachId = "outreach-jane-step-1";
let campaignState = "ready";
let approved = false;
let sent = false;
let outcome: string | null = null;

async function capture(page: import("@playwright/test").Page, name: string) {
  if (process.env.WO030_SCREENSHOTS !== "1") return;
  await page.screenshot({
    path: `../../docs/07-sprints/images/wo-030/${name}.png`,
    fullPage: true,
  });
}

const contacts = {
  items: [
    {
      id: "contact-jane",
      organisationId: "org-1",
      companyId: "company-northstar",
      firstName: "Jane",
      lastName: "Smith",
      email: "jane.smith@northstar.example",
      phone: null,
      jobTitle: "Chief Information Officer",
      linkedinUrl: null,
      ownerUserId: "user-1",
      createdAt: "2026-08-25T00:00:00Z",
      updatedAt: "2026-08-25T00:00:00Z",
    },
    {
      id: "contact-sam",
      organisationId: "org-1",
      companyId: "company-river",
      firstName: "Sam",
      lastName: "Rivera",
      email: null,
      phone: null,
      jobTitle: "Technology Director",
      linkedinUrl: null,
      ownerUserId: "user-1",
      createdAt: "2026-08-25T00:00:00Z",
      updatedAt: "2026-08-25T00:00:00Z",
    },
  ],
  page: 1,
  pageSize: 50,
  total: 2,
  pages: 1,
};

const steps = [
  {
    id: "sequence-1",
    stepOrder: 1,
    delayDays: 0,
    objective: "introduction",
    contentStrategy: "source_backed_value",
    enabled: true,
  },
  {
    id: "sequence-2",
    stepOrder: 2,
    delayDays: 4,
    objective: "follow_up",
    contentStrategy: "truthful_follow_up",
    enabled: true,
  },
  {
    id: "sequence-3",
    stepOrder: 3,
    delayDays: 5,
    objective: "different_angle",
    contentStrategy: "source_backed_new_angle",
    enabled: true,
  },
  {
    id: "sequence-4",
    stepOrder: 4,
    delayDays: 7,
    objective: "final_follow_up",
    contentStrategy: "respectful_close",
    enabled: true,
  },
];

function campaign() {
  const active = campaignState === "active";
  const launched = !["draft", "ready"].includes(campaignState);
  return {
    id: campaignId,
    versionId: "campaign-version-1",
    version: 1,
    name: "Australian Multi-Site CIO Outreach",
    purpose: "Book respectful introductory meetings",
    state: campaignState,
    approvalMode: "review_each_send",
    ownerUserId: "user-1",
    senderUserId: "user-1",
    sourceType: "manual_contacts",
    senderTimezone: "Australia/Sydney",
    sendDays: [1, 2, 3, 4, 5],
    sendWindowStartMinutes: 510,
    sendWindowEndMinutes: 1020,
    stopOnActiveOpportunity: true,
    policyVersion: active ? 1 : null,
    audienceCount: 2,
    eligibleCount: 1,
    blockedCount: 1,
    steps,
    audience: [
      {
        id: "audience-jane",
        contactId: "contact-jane",
        companyId: "company-northstar",
        recipientName: "Jane Smith",
        recipientEmail: "jane.smith@northstar.example",
        recipientTrust: "provider_supplied",
        eligible: true,
        eligibilityCode: "eligible",
        eligibilityReason: "Allowed under the configured organisation policy.",
      },
      {
        id: "audience-sam",
        contactId: "contact-sam",
        companyId: "company-river",
        recipientName: "Sam Rivera",
        recipientEmail: null,
        recipientTrust: "unknown",
        eligible: false,
        eligibilityCode: "no_business_email",
        eligibilityReason: "This Contact has no supported business email.",
      },
    ],
    metrics: {
      recipients: active ? 1 : 0,
      active: active && !outcome ? 1 : 0,
      completed: 0,
      stopped: outcome ? 1 : 0,
      blocked: 0,
      needsAttention: 0,
      messagesSent: sent ? 1 : 0,
      messagesReadyForReview: active && !sent ? 1 : 0,
      messagesFailed: 0,
      repliesReported: outcome === "replied" ? 1 : 0,
      meetingsReported: 0,
    },
    canManage: true,
    canLaunch: !launched,
    campaignAutoSendAllowed: true,
    simulationOnly: true,
    productionMailboxAvailable: false,
    launchWarning: launched ? "This campaign runs in simulation only." : null,
    needsAttentionReason: null,
    launchedAt: launched ? "2026-08-26T01:00:00Z" : null,
    createdAt: "2026-08-26T00:30:00Z",
    updatedAt: "2026-08-26T01:00:00Z",
  };
}

function outreach(state = approved ? "approved" : "draft") {
  return {
    id: outreachId,
    actionId: "action-jane-step-1",
    contactId: "contact-jane",
    purpose: "introduction",
    state,
    currentVersion: 1,
    approvedVersion: approved ? 1 : null,
    version: {
      id: "outreach-version-1",
      version: 1,
      subject: "Northstar's multi-site technology programme",
      body: "Hi Jane,\n\nNorthstar's expansion and your technology consolidation work prompted me to get in touch. We help multi-site teams manage access consistently.\n\nWould a short conversation next week be useful?\n\nRegards,\nAlex",
      senderName: "Alex Morgan",
      senderEmail: "alex@example.test",
      recipientName: "Jane Smith",
      recipientEmail: "jane.smith@northstar.example",
      recipientTrust: "provider_supplied",
      creationType: "generated",
      composerVersion: "outreach_campaign_deterministic_v1",
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
          url: "https://northstar.example/news",
        },
        {
          id: "source-offering",
          sourceType: "approved_seller_context",
          sourceId: "org-1",
          label: "Approved seller offering: Multi-site Access Management",
          trustState: "approved",
          publisher: null,
          publishedAt: null,
          url: null,
        },
      ],
      warnings: [],
      createdAt: "2026-08-26T01:00:00Z",
    },
    contactability: {
      state: "allowed",
      allowed: true,
      reason: "Allowed under policy.",
      trustState: "provider_supplied",
      permissionAssessedSeparately: true,
    },
    relationshipWarning: null,
    execution: null,
    createdAt: "2026-08-26T01:00:00Z",
    updatedAt: "2026-08-26T01:00:00Z",
  };
}

function enrollment() {
  return {
    id: enrollmentId,
    campaignId,
    contactId: "contact-jane",
    companyId: "company-northstar",
    recipientName: "Jane Smith",
    recipientEmail: "jane.smith@northstar.example",
    recipientTrust: "provider_supplied",
    state: outcome ? "stopped" : "active",
    currentStepOrder: sent ? 2 : 1,
    nextScheduledAt: sent ? "2026-08-31T00:30:00Z" : "2026-08-26T01:00:00Z",
    stopReason: outcome ? `seller_reported_${outcome}` : null,
    outcome,
    outcomeProvenance: outcome ? "seller_reported" : null,
    steps: sent
      ? [
          {
            id: "enrollment-step-1",
            stepOrder: 1,
            objective: "introduction",
            scheduledAt: "2026-08-26T01:00:00Z",
            state: "sent",
            safeStatusCode: "simulated",
            outreachMessageId: outreachId,
            preparedAt: "2026-08-26T00:45:00Z",
            sentAt: "2026-08-26T01:30:00Z",
          },
          {
            id: "enrollment-step-2",
            stepOrder: 2,
            objective: "follow_up",
            scheduledAt: "2026-08-31T00:30:00Z",
            state: outcome ? "cancelled" : "pending",
            safeStatusCode: outcome ? `seller_reported_${outcome}` : null,
            outreachMessageId: null,
            preparedAt: null,
            sentAt: null,
          },
        ]
      : [
          {
            id: "enrollment-step-1",
            stepOrder: 1,
            objective: "introduction",
            scheduledAt: "2026-08-26T01:00:00Z",
            state: "ready_for_review",
            safeStatusCode: null,
            outreachMessageId: outreachId,
            preparedAt: "2026-08-26T00:45:00Z",
            sentAt: null,
          },
        ],
    currentOutreach: sent ? null : outreach(),
    createdAt: "2026-08-26T01:00:00Z",
    updatedAt: "2026-08-26T01:00:00Z",
  };
}

test.beforeEach(() => {
  campaignState = "ready";
  approved = false;
  sent = false;
  outcome = null;
});

test("builds, reviews, launches and sends a bounded flagship campaign", async ({
  page,
}) => {
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/prospect/availability")
      return route.fulfill({
        json: {
          moduleKey: "prospect",
          state: "available",
          enabled: true,
          canManage: true,
          message: "Available",
        },
      });
    if (path === "/api/v1/engage/availability")
      return route.fulfill({
        json: {
          moduleKey: "engage",
          state: "available",
          enabled: true,
          canManage: true,
          message: "Available",
        },
      });
    if (path === "/api/v1/engage/campaigns" && request.method() === "GET")
      return route.fulfill({
        json: {
          items: [],
          total: 0,
          canCreate: true,
          simulationOnly: true,
          productionMailboxAvailable: false,
        },
      });
    if (path === "/api/v1/contacts") return route.fulfill({ json: contacts });
    if (path === "/api/v1/engage/policy")
      return route.fulfill({
        json: {
          version: 1,
          configured: true,
          outboundEnabled: true,
          providerSuppliedEmailAllowed: true,
          campaignAutoSendAllowed: true,
          cooldownHours: 72,
          maxDailySendsUser: 25,
          maxDailySendsOrg: 100,
          requireOptOutMechanism: false,
          offeringName: "Multi-site Access Management",
          valueProposition: "Consistent access operations",
          approvedCta: "Discuss next week?",
          canManage: true,
          complianceNotice: "Organisation remains responsible.",
        },
      });
    if (path === "/api/v1/engage/campaigns" && request.method() === "POST") {
      const body = request.postDataJSON() as {
        contactIds: string[];
        steps: unknown[];
      };
      expect(body.contactIds).toEqual(["contact-jane", "contact-sam"]);
      expect(body.steps).toHaveLength(4);
      return route.fulfill({ status: 201, json: campaign() });
    }
    if (path === `/api/v1/engage/campaigns/${campaignId}`)
      return route.fulfill({ json: campaign() });
    if (path === `/api/v1/engage/campaigns/${campaignId}/launch`) {
      expect(request.postDataJSON()).toEqual({
        expectedVersion: 1,
        confirmed: true,
        autoSendConfirmed: false,
      });
      campaignState = "active";
      return route.fulfill({ json: campaign() });
    }
    if (path === `/api/v1/engage/campaigns/${campaignId}/pause`) {
      campaignState = "paused";
      return route.fulfill({ json: campaign() });
    }
    if (path === `/api/v1/engage/campaigns/${campaignId}/resume`) {
      campaignState = "active";
      return route.fulfill({ json: campaign() });
    }
    if (path === `/api/v1/engage/campaigns/${campaignId}/enrollments`)
      return route.fulfill({ json: { items: [enrollment()], total: 1 } });
    if (path === `/api/v1/engage/enrollments/${enrollmentId}`)
      return route.fulfill({ json: enrollment() });
    if (path === `/api/v1/engage/outreach/${outreachId}/approve`) {
      approved = true;
      return route.fulfill({ json: outreach("approved") });
    }
    if (path === "/api/v1/actions/action-jane-step-1/execution-options")
      return route.fulfill({
        json: {
          items: [
            {
              connectionId: "connection-mock",
              connectorKey: "mock_email",
              connectorDisplayName: "Mock Email",
              capability: "send_email",
              riskClass: "external_customer_facing",
              executionMode: "simulation",
              simulationOnly: true,
            },
          ],
          total: 1,
        },
      });
    if (path === `/api/v1/engage/outreach/${outreachId}/execution-preview`)
      return route.fulfill({
        json: {
          id: "preview-1",
          actionProposalId: "action-jane-step-1",
          actionVersion: 1,
          connectionId: "connection-mock",
          connectorKey: "mock_email",
          connectorDisplayName: "Mock Email",
          capability: "send_email",
          riskClass: "external_customer_facing",
          executionMode: "simulation",
          simulationOnly: true,
          readiness: "ready",
          summary: "Review exact email",
          confirmationLabel: "Send email",
          previewFingerprint: "a".repeat(64),
          content: {
            kind: "email",
            senderName: "Alex Morgan",
            senderEmail: "alex@example.test",
            recipientName: "Jane Smith",
            recipient: "jane.smith@northstar.example",
            subject: "Northstar's multi-site technology programme",
            body: "Exact approved body",
            action: "send_email",
          },
          expiresAt: "2026-08-26T02:00:00Z",
          createdAt: "2026-08-26T01:00:00Z",
        },
      });
    if (path === `/api/v1/engage/outreach/${outreachId}/send`) {
      sent = true;
      return route.fulfill({
        status: 202,
        json: {
          id: "execution-1",
          actionProposalId: "action-jane-step-1",
          actionVersion: 1,
          connectionId: "connection-mock",
          connectorKey: "mock_email",
          connectorDisplayName: "Mock Email",
          capability: "send_email",
          riskClass: "external_customer_facing",
          executionStatus: "queued",
          executionMode: "simulation",
          simulationOnly: true,
          confirmedByUserId: "user-1",
          confirmedAt: "2026-08-26T01:00:00Z",
          startedAt: null,
          completedAt: null,
          failedAt: null,
          safeFailureCode: null,
          externalResultId: null,
          safeMessage: "The email simulation is queued.",
          attemptCount: 0,
          maxAttempts: 3,
          nextAttemptAt: null,
          canReconcile: false,
          createdAt: "2026-08-26T01:00:00Z",
          updatedAt: "2026-08-26T01:00:00Z",
        },
      });
    }
    if (path === `/api/v1/engage/enrollments/${enrollmentId}/outcome`) {
      outcome = (request.postDataJSON() as { outcome: string }).outcome;
      campaignState = "completed";
      return route.fulfill({ json: enrollment() });
    }
    return route.fulfill({
      status: 404,
      json: {
        code: "not_mocked",
        message: `Not mocked: ${path}`,
        requestId: "e2e",
      },
    });
  });

  await page.goto("/campaigns");
  await expect(
    page.getByRole("heading", { name: "Start with a small, exact audience" }),
  ).toBeVisible();
  await capture(page, "campaign-first-use-desktop");
  await page.getByRole("link", { name: "Create campaign" }).first().click();
  await page.getByLabel(/Jane Smith/u).check();
  await page.getByLabel(/Sam Rivera/u).check();
  await capture(page, "campaign-builder-desktop");
  await page.getByLabel("Approved campaign auto-send").check();
  await capture(page, "campaign-auto-send-warning-desktop");
  await page.getByLabel("Review each send").check();
  await page.getByRole("button", { name: "Review audience" }).click();
  await expect(
    page.getByRole("heading", { name: "Audience review" }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", {
      name: "This Contact has no supported business email.",
    }),
  ).toBeVisible();
  await capture(page, "campaign-audience-review-desktop");
  await page.getByLabel(/reviewed the exact audience/u).check();
  await page
    .getByRole("button", { name: "Launch to 1 eligible Contact" })
    .click();
  await expect(
    page.getByText(
      "Campaign launched. Recipient work will be prepared inside the configured send window.",
    ),
  ).toBeVisible();
  await capture(page, "campaign-active-desktop");
  await page.setViewportSize({ width: 390, height: 844 });
  await capture(page, "campaign-summary-mobile");
  const mobileScrollWidth = await page.evaluate(
    () => document.documentElement.scrollWidth,
  );
  expect(mobileScrollWidth).toBeLessThanOrEqual(390);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText("Paused", { exact: true })).toBeVisible();
  await capture(page, "campaign-paused-desktop");
  await page.getByRole("button", { name: "Resume" }).click();
  await page.getByRole("link", { name: /Jane Smith/u }).click();
  await expect(
    page.getByRole("heading", { name: "Exact personalised message" }),
  ).toBeVisible();
  await expect(page.getByText(/Northstar announced expansion/u)).toBeVisible();
  await capture(page, "campaign-recipient-review-desktop");
  await page.setViewportSize({ width: 390, height: 844 });
  await capture(page, "campaign-recipient-review-mobile");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "Approve exact message" }).click();
  await page.getByRole("button", { name: "Review exact send preview" }).click();
  await expect(page.getByText("Exact approved body")).toBeVisible();
  await page.getByRole("button", { name: "Send email" }).click();
  await expect(page.getByText(/Step 2 is scheduled/u)).toBeVisible();
  await expect(page.getByText(/Scheduled 31 Aug 2026/u)).toBeVisible();
  await page.getByRole("button", { name: "Report replied" }).click();
  await expect(page.getByText("Seller reported · Replied")).toBeVisible();
  await page.getByRole("link", { name: "← Campaign", exact: true }).click();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await capture(page, "campaign-completed-desktop");
});
