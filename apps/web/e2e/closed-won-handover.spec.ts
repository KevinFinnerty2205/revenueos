import { expect, test, type Page } from "@playwright/test";

const opportunityId = "opportunity-handover";

const emptyContent = {
  schemaVersion: 1,
  executiveSummary: [],
  customerObjectives: [],
  whyTheyBought: [],
  commercialScope: [],
  keyStakeholders: [],
  commitments: [],
  successCriteria: [],
  implementationExpectations: [],
  risks: [],
  openItems: [],
  timeline: [],
  nextActions: [],
};

function item(
  id: string,
  text: string,
  authorityType:
    | "customer_evidence"
    | "seller_confirmed"
    | "commercial_record"
    | "customer_facing_approved"
    | "system_derived"
    | "inference",
  sourceIds: string[],
) {
  return {
    id,
    text,
    authorityType,
    sourceIds,
    confirmedByUserId: authorityType === "seller_confirmed" ? "user-1" : null,
    confirmedAt:
      authorityType === "seller_confirmed" ? "2026-09-08T01:00:00Z" : null,
    owner: null,
    dueDate: null,
    actionStatus: null,
    riskKind: authorityType === "inference" ? "system_inference" : null,
  };
}

const sources = [
  {
    id: "source-opportunity",
    sourceType: "opportunity",
    sourceId: opportunityId,
    sourceVersionId: null,
    sourceVersion: null,
    authorityType: "commercial_record",
    label: "Canonical Opportunity record",
    sourceFingerprint: "a".repeat(64),
    pinnedAt: "2026-09-08T00:00:00Z",
  },
  {
    id: "source-deal-room",
    sourceType: "deal_room",
    sourceId: "deal-room-1",
    sourceVersionId: "deal-room-revision-2",
    sourceVersion: 2,
    authorityType: "customer_facing_approved",
    label: "Published Deal Room revision 2",
    sourceFingerprint: "b".repeat(64),
    pinnedAt: "2026-09-08T00:00:00Z",
  },
  {
    id: "source-evidence",
    sourceType: "evidence",
    sourceId: "evidence-1",
    sourceVersionId: "evidence-snapshot-3",
    sourceVersion: 3,
    authorityType: "customer_evidence",
    label: "Reviewed Evidence: implementation workshop",
    sourceFingerprint: "c".repeat(64),
    pinnedAt: "2026-09-08T00:00:00Z",
  },
];

function revision(
  status: "draft" | "in_review" | "approved" | "superseded" | "retired",
  revisionNumber = 1,
) {
  const inference = status === "in_review";
  return {
    id: `handover-revision-${revisionNumber}`,
    handoverId: "handover-1",
    opportunityId,
    revision: revisionNumber,
    status,
    contentSchemaVersion: 1,
    content: {
      ...emptyContent,
      executiveSummary: [
        item(
          `summary-${revisionNumber}`,
          "Northstar is transitioning into a reviewed implementation programme.",
          "customer_facing_approved",
          ["source-deal-room"],
        ),
      ],
      commercialScope: [
        item(
          `scope-${revisionNumber}`,
          "Canonical Opportunity value: AUD 125000.00. This is an Opportunity record, not a contract.",
          "commercial_record",
          ["source-opportunity"],
        ),
      ],
      commitments: [
        item(
          `commitment-${revisionNumber}`,
          "The customer requested a named implementation lead before kickoff.",
          "customer_evidence",
          ["source-evidence"],
        ),
      ],
      risks: inference
        ? [
            item(
              "risk-inference",
              "Possible unverified data-migration dependency.",
              "inference",
              [],
            ),
          ]
        : [],
      nextActions: [
        {
          ...item(
            `action-${revisionNumber}`,
            "Confirm the kickoff attendees.",
            "seller_confirmed",
            [],
          ),
          owner: "Alex Morgan",
          dueDate: "2026-09-15",
          actionStatus: "open",
        },
      ],
    },
    sources,
    lockVersion: 1,
    approvalBlockers: inference
      ? ["risks: confirm or remove the inference before approval."]
      : [],
    createdByUserId: "user-1",
    submittedAt: status === "draft" ? null : "2026-09-08T01:00:00Z",
    approvedByUserId:
      status === "approved" || status === "superseded" || status === "retired"
        ? "user-1"
        : null,
    approvedAt:
      status === "approved" || status === "superseded" || status === "retired"
        ? "2026-09-08T02:00:00Z"
        : null,
    supersededAt: status === "superseded" ? "2026-09-08T03:00:00Z" : null,
    retiredAt: status === "retired" ? "2026-09-08T04:00:00Z" : null,
    retirementReason: status === "retired" ? "opportunity_reopened" : null,
    createdAt: "2026-09-08T00:00:00Z",
    updatedAt: "2026-09-08T02:00:00Z",
  };
}

async function routeShell(page: Page) {
  await page.route("http://localhost:8000/api/v1/me", (route) =>
    route.fulfill({
      json: {
        user: {
          id: "user-1",
          externalAuthId: "user_dev_001",
          displayName: "Alex Morgan",
          email: "alex@example.test",
        },
        organisation: {
          id: "organisation-1",
          name: "Synthetic Revenue Team",
          slug: "synthetic-revenue-team",
        },
        role: "admin",
        authMode: "mock",
        requestId: "request-handover-e2e",
      },
    }),
  );
  await page.route("http://localhost:8000/api/v1/beta/capabilities", (route) =>
    route.fulfill({
      json: {
        featureFlags: { opportunityWorkspace: true },
        noticeVersion: 1,
        maxTranscriptCharacters: 200000,
      },
    }),
  );
}

async function routeOpportunity(page: Page) {
  await page.route(
    `http://localhost:8000/api/v1/opportunities/${opportunityId}/workspace`,
    (route) =>
      route.fulfill({
        json: {
          opportunity: {
            id: opportunityId,
            companyId: "company-1",
            companyName: "Northstar Operations",
            name: "National operations rollout",
            stage: "proposal",
            status: "open",
            estimatedValue: "125000.00",
            currency: "AUD",
            expectedCloseDate: "2026-09-30",
            ownerUserId: "user-1",
            ownerName: "Alex Morgan",
            description: "Reviewed synthetic transition scenario.",
            createdAt: "2026-09-01T00:00:00Z",
            updatedAt: "2026-09-08T00:00:00Z",
          },
          reasoning: {
            state: "not_ready",
            message: "Longitudinal reasoning is not available.",
            latest: null,
            history: [],
          },
          latestMeeting: null,
          recentMeetings: [],
          intelligence: null,
          reportedIntelligence: null,
          visualIntelligence: null,
          latestInteractionCapture: null,
          methodology: {
            state: "not_configured",
            generationAvailable: false,
            needsRefresh: false,
            safeMessage: "No methodology selected.",
            definition: null,
            projectionId: null,
            projection: null,
            generatedAt: null,
          },
          intelligenceSectionsAvailable: 0,
          partialData: false,
          generatedAt: "2026-09-08T00:00:00Z",
        },
      }),
  );
  await page.route("http://localhost:8000/api/v1/meetings**", (route) =>
    route.fulfill({
      json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
    }),
  );
  await page.route(
    `http://localhost:8000/api/v1/opportunities/${opportunityId}/actions`,
    (route) => route.fulfill({ json: { items: [], total: 0 } }),
  );
  await page.route(
    `http://localhost:8000/api/v1/opportunities/${opportunityId}/deal-room`,
    (route) =>
      route.fulfill({
        json: {
          room: null,
          businessCases: [],
          presentations: [],
          entitlement: "create",
          creditsRequired: false,
        },
      }),
  );
  await page.route(
    `http://localhost:8000/api/v1/crm/records/opportunity/${opportunityId}`,
    (route) =>
      route.fulfill({
        json: {
          entityType: "opportunity",
          entityId: opportunityId,
          title: "National operations rollout",
          ownerUserId: "user-1",
          ownerName: "Alex Morgan",
          archivedAt: null,
          recordUpdatedAt: "2026-09-08T00:00:00Z",
          mode: "native",
          crmEnabled: true,
          canManage: true,
          customFieldsReadOnly: false,
          fieldAuthority: {},
          coreFields: [],
          customFields: [],
          history: [],
          activity: [],
        },
      }),
  );
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 900 },
  { name: "390px mobile", width: 390, height: 844 },
]) {
  test(`Closed-Won Handover lifecycle remains reviewed and source-visible on ${viewport.name}`, async ({
    page,
  }) => {
    await routeShell(page);
    await routeOpportunity(page);
    let state: "not_prepared" | "draft" | "in_review" | "approved" =
      "not_prepared";

    await page.route(
      `http://localhost:8000/api/v1/opportunities/${opportunityId}/handover**`,
      async (route) => {
        const request = route.request();
        const path = new URL(request.url()).pathname;
        if (request.method() === "POST" && path.endsWith("/prepare")) {
          state = "draft";
        }
        if (state === "not_prepared") {
          await route.fulfill({
            json: {
              handoverId: null,
              opportunityId,
              opportunityStatus: "open",
              handoverLockVersion: null,
              activeRevision: null,
              currentApprovedRevision: null,
              history: [],
              canManage: true,
              canApprove: true,
              entitlement: "create",
              creditsRequired: false,
              aiDrafting: "not_used",
            },
          });
          return;
        }
        const active =
          state === "draft"
            ? revision("draft")
            : state === "in_review"
              ? revision("in_review")
              : revision("approved", 3);
        const history =
          state === "approved"
            ? [active, revision("superseded", 2), revision("retired", 1)]
            : [active];
        await route.fulfill({
          json: {
            handoverId: "handover-1",
            opportunityId,
            opportunityStatus: state === "approved" ? "won" : "open",
            handoverLockVersion: 1,
            activeRevision: active,
            currentApprovedRevision: state === "approved" ? active : null,
            history,
            canManage: true,
            canApprove: true,
            entitlement: "create",
            creditsRequired: false,
            aiDrafting: "not_used",
          },
        });
      },
    );

    await page.setViewportSize(viewport);
    await page.goto(`/opportunities/${opportunityId}`);
    await expect(
      page.getByRole("heading", { name: "Prepare a Closed-Won Handover" }),
    ).toBeVisible();
    await expect(page.getByText(/does not call an AI provider/i)).toBeVisible();
    await page.getByRole("button", { name: "Prepare handover draft" }).click();
    await expect(
      page.getByRole("heading", { name: "Closed-Won Handover · revision 1" }),
    ).toBeVisible();
    await expect(
      page.getByText("Customer Evidence", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/No Credits required/i).last()).toBeVisible();

    state = "in_review";
    await page.reload();
    await expect(
      page.getByText("Review required before approval"),
    ).toBeVisible();
    await expect(page.getByText("Inference — review required")).toBeVisible();
    await expect(
      page.getByText(/canonical Opportunity status is Closed Won/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Approve immutable handover" }),
    ).toBeDisabled();

    state = "approved";
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Closed-Won Handover · revision 3" }),
    ).toBeVisible();
    await page.getByText(/Revision history \(3\)/).click();
    await expect(page.getByText("superseded", { exact: true })).toBeVisible();
    await expect(page.getByText("retired", { exact: true })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      ),
    ).toBeLessThanOrEqual(0);
    await page.keyboard.press("Tab");
    await expect(page.locator(":focus")).toBeVisible();
  });
}
