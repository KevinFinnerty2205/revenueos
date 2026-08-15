import { expect, test } from "@playwright/test";

const opportunityId = "opportunity-action";

function proposal(status: "proposed" | "approved" = "proposed") {
  return {
    id: "action-1",
    organisationId: "organisation-1",
    opportunityId,
    interactionId: "interaction-1",
    actionType: "follow_up_email",
    status,
    priority: "high",
    audience: "customer_facing",
    riskClass: "external_customer_facing",
    currentVersion: 1,
    approvedVersion: status === "approved" ? 1 : null,
    title: "Review the customer follow-up",
    description: "Review the grounded draft before taking any external action.",
    proposedDueAt: "2026-08-18T02:00:00Z",
    targetEntityType: "contact",
    targetEntityId: "contact-1",
    proposedPayload: {
      kind: "follow_up_email",
      draftArtifactId: "artifact-1",
      recipientContactId: null,
      recipientEmail: null,
      recipientConfirmed: false,
      subject: "Security review next steps",
      body: "Hello Jordan,\n\nThank you for the discussion.",
    },
    sourceRefs: [
      {
        sourceType: "ai_artifact",
        sourceId: "artifact-1",
        itemKey: "follow_up_email",
        label: "Final validated Follow-up Email",
        origin: "validated_intelligence",
      },
    ],
    provenanceSummary: "Derived from final validated Meeting Intelligence.",
    generatedAt: "2026-08-15T02:00:00Z",
    versionCreatedAt: "2026-08-15T02:00:00Z",
    createdByUserId: "user-1",
    reviewedByUserId: status === "approved" ? "user-1" : null,
    reviewedAt: status === "approved" ? "2026-08-15T03:00:00Z" : null,
    approvedAt: status === "approved" ? "2026-08-15T03:00:00Z" : null,
    rejectedAt: null,
    rejectionReasonCode: null,
    supersedesActionId: null,
    completedByUserId: null,
    completedAt: null,
    executionState: "not_executed",
    sendReady: false,
  };
}

test("reviews a customer-facing Action without exposing external execution", async ({
  page,
}) => {
  let status: "proposed" | "approved" = "proposed";
  let approvalPayload: Record<string, unknown> | null = null;

  await page.route(
    "http://localhost:8000/api/v1/beta/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          featureFlags: {
            opportunityWorkspace: true,
            actionLayer: true,
            actionManualCompletion: true,
          },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
  await page.route(
    `http://localhost:8000/api/v1/opportunities/${opportunityId}/workspace`,
    async (route) => {
      await route.fulfill({
        json: {
          opportunity: {
            id: opportunityId,
            companyId: "company-1",
            companyName: "Acme Australia",
            name: "Platform expansion",
            stage: "proposal",
            status: "open",
            estimatedValue: "125000.00",
            currency: "AUD",
            expectedCloseDate: "2026-09-30",
            ownerUserId: "user-1",
            ownerName: "Alex Morgan",
            description: "Synthetic opportunity for Action review.",
            createdAt: "2026-08-01T00:00:00Z",
            updatedAt: "2026-08-15T00:00:00Z",
          },
          reasoning: {
            state: "not_generated",
            message: "No longitudinal changes generated.",
            latest: null,
            history: [],
          },
          latestMeeting: null,
          recentMeetings: [],
          intelligence: null,
          reportedIntelligence: null,
          visualIntelligence: null,
          latestInteractionCapture: null,
          intelligenceSectionsAvailable: 0,
          partialData: false,
          generatedAt: "2026-08-15T00:00:00Z",
        },
      });
    },
  );
  await page.route("http://localhost:8000/api/v1/meetings**", async (route) => {
    await route.fulfill({
      json: { items: [], page: 1, pageSize: 100, total: 0, pages: 0 },
    });
  });
  await page.route(
    `http://localhost:8000/api/v1/opportunities/${opportunityId}/actions`,
    async (route) => {
      await route.fulfill({ json: { items: [proposal(status)], total: 1 } });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/actions/action-1/approve",
    async (route) => {
      approvalPayload = route.request().postDataJSON() as Record<
        string,
        unknown
      >;
      status = "approved";
      await route.fulfill({ json: proposal("approved") });
    },
  );
  await page.route(
    `http://localhost:8000/api/v1/evidence/opportunities/${opportunityId}`,
    async (route) => route.fulfill({ json: [] }),
  );
  await page.route(
    "http://localhost:8000/api/v1/evidence/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          documentEvidence: true,
          emailEvidence: true,
          supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
          emailProviderImport: false,
          documentProviderImport: false,
          safeMessage: "Manual evidence only.",
        },
      });
    },
  );

  await page.goto(`/opportunities/${opportunityId}`);
  const actions = page.getByRole("region", { name: "Recommended Actions" });
  await expect(
    actions.getByText("Customer-facing — review carefully"),
  ).toBeVisible();
  await expect(
    actions.getByText(/Draft only — no recipient is treated as confirmed/i),
  ).toBeVisible();
  await expect(
    actions.getByRole("button", { name: /^send|sync|schedule$/i }),
  ).toHaveCount(0);

  if (process.env.CAPTURE_WO_021_SCREENSHOT === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-021-action-layer.png",
      fullPage: true,
    });
  }

  await actions
    .getByRole("button", { name: "Approve — do not execute" })
    .click();
  await expect(
    actions.getByText(/Nothing was sent, synced or executed/i),
  ).toBeVisible();
  expect(approvalPayload).toEqual({ expectedVersion: 1 });
  await actions.getByRole("tab", { name: "Approved (1)" }).click();
  await expect(actions.getByText("Approved — not yet executed")).toBeVisible();
  await expect(
    actions.getByRole("button", { name: /^send|sync|schedule$/i }),
  ).toHaveCount(0);
});
