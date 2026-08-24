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
      recipientContactId: "contact-1",
      recipientEmail: "jordan@example.com",
      recipientConfirmed: true,
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

test("reviews, confirms and persists a customer-facing Action simulation", async ({
  page,
}) => {
  let status: "proposed" | "approved" = "proposed";
  let approvalPayload: Record<string, unknown> | null = null;
  let executionPayload: Record<string, unknown> | null = null;
  let executionCompleted = false;
  let connectionCreated = false;
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["localhost", "127.0.0.1"].includes(url.hostname)) {
      externalRequests.push(request.url());
    }
  });

  await page.route(
    "http://localhost:8000/api/v1/beta/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          featureFlags: {
            opportunityWorkspace: true,
            actionLayer: true,
            actionManualCompletion: true,
            integrations: true,
            actionExecution: true,
            mockConnectors: true,
          },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
  await page.route("http://localhost:8000/api/v1/beta/admin", async (route) => {
    await route.fulfill({
      json: {
        organisation: {
          id: "organisation-1",
          name: "Acme Revenue Team",
          slug: "acme-revenue-team",
        },
        members: [],
        retention: { policy: "days_90", defaultApplied: true },
        noticeVersion: 1,
        acknowledgementCount: 1,
        activeMemberCount: 1,
        featureFlags: {
          integrations: true,
          actionExecution: true,
          mockConnectors: true,
          dataExport: false,
          organisationDeletion: false,
        },
        usage: {
          date: "2026-08-15",
          generations: 0,
          generationLimit: 100,
          providerRequests: 0,
          providerRequestLimit: 200,
          estimatedCostAvailable: false,
        },
        recentEvents: [],
        dataRequests: [],
      },
    });
  });
  await page.route("http://localhost:8000/api/v1/me", async (route) => {
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
          name: "Acme Revenue Team",
          slug: "acme-revenue-team",
        },
        role: "admin",
        authMode: "mock",
        requestId: "request-action-e2e",
      },
    });
  });
  await page.route(
    "http://localhost:8000/api/v1/integrations",
    async (route) => {
      await route.fulfill({
        json: {
          connectors: [
            {
              connectorKey: "mock_email",
              displayName: "Mock Email",
              providerFamily: "mock",
              supportedCapabilities: ["send_email"],
              authenticationType: "mock_local",
              executionRiskClasses: ["external_customer_facing"],
              configurationSchemaVersion: 1,
              executionMode: "simulation",
              available: true,
              simulationOnly: true,
            },
          ],
          executionMode: "simulation",
          externalActionsEnabled: false,
        },
      });
    },
  );
  const connection = {
    id: "connection-1",
    connectorKey: "mock_email",
    displayName: "Mock Email",
    connectionStatus: "active",
    supportedCapabilities: ["send_email"],
    capabilityState: ["send_email"],
    createdByUserId: "user-1",
    connectedAt: "2026-08-15T03:00:00Z",
    lastVerifiedAt: "2026-08-15T03:00:00Z",
    revokedAt: null,
    metadataVersion: 1,
    executionMode: "simulation",
    simulationOnly: true,
    createdAt: "2026-08-15T03:00:00Z",
    updatedAt: "2026-08-15T03:00:00Z",
  };
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections",
    async (route) => {
      if (route.request().method() === "POST") {
        connectionCreated = true;
        await route.fulfill({ status: 201, json: connection });
        return;
      }
      await route.fulfill({
        json: {
          items: connectionCreated ? [connection] : [],
          total: connectionCreated ? 1 : 0,
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
          methodology: {
            state: "not_configured",
            definition: null,
            projectionId: null,
            projection: null,
            generationAvailable: false,
            safeMessage:
              "Your organisation has not selected a sales methodology.",
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
    "http://localhost:8000/api/v1/actions/action-1/execution-options",
    async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              connectionId: "connection-1",
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
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/actions/action-1/execution-preview",
    async (route) => {
      await route.fulfill({
        json: {
          id: "preview-1",
          actionProposalId: "action-1",
          actionVersion: 1,
          connectionId: "connection-1",
          connectorKey: "mock_email",
          connectorDisplayName: "Mock Email",
          capability: "send_email",
          riskClass: "external_customer_facing",
          executionMode: "simulation",
          simulationOnly: true,
          readiness: "ready",
          summary: "Simulate sending this approved email.",
          confirmationLabel: "Send email",
          previewFingerprint: "a".repeat(64),
          content: {
            kind: "email",
            recipient: "jordan@example.com",
            subject: "Security review next steps",
            body: "Hello Jordan,\n\nThank you for the discussion.",
            action: "send_email",
          },
          expiresAt: "2026-08-15T03:10:00Z",
          createdAt: "2026-08-15T03:00:00Z",
        },
      });
    },
  );
  const execution = () => ({
    id: "execution-1",
    actionProposalId: "action-1",
    actionVersion: 1,
    connectionId: "connection-1",
    connectorKey: "mock_email",
    connectorDisplayName: "Mock Email",
    capability: "send_email",
    riskClass: "external_customer_facing",
    executionStatus: executionCompleted ? "simulated_success" : "queued",
    executionMode: "simulation",
    simulationOnly: true,
    confirmedByUserId: "user-1",
    confirmedAt: "2026-08-15T03:01:00Z",
    startedAt: executionCompleted ? "2026-08-15T03:01:01Z" : null,
    completedAt: executionCompleted ? "2026-08-15T03:01:02Z" : null,
    failedAt: null,
    safeFailureCode: null,
    externalResultId: executionCompleted ? "mock_email_result_1" : null,
    attemptCount: executionCompleted ? 1 : 0,
    retryable: false,
    safeMessage: executionCompleted
      ? "Simulation completed. No external action occurred."
      : "Simulation queued. No external action has occurred.",
    createdAt: "2026-08-15T03:01:00Z",
    updatedAt: "2026-08-15T03:01:02Z",
    attempts: executionCompleted
      ? [
          {
            attemptNumber: 1,
            status: "simulated_success",
            safeFailureCode: null,
            externalResultId: "mock_email_result_1",
            startedAt: "2026-08-15T03:01:01Z",
            completedAt: "2026-08-15T03:01:02Z",
            durationMs: 1000,
          },
        ]
      : [],
  });
  await page.route(
    "http://localhost:8000/api/v1/actions/action-1/executions",
    async (route) => {
      await route.fulfill({
        json: {
          items: executionCompleted ? [execution()] : [],
          total: executionCompleted ? 1 : 0,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/actions/action-1/execute",
    async (route) => {
      executionPayload = route.request().postDataJSON() as Record<
        string,
        unknown
      >;
      await route.fulfill({ status: 202, json: execution() });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/executions/execution-1",
    async (route) => {
      executionCompleted = true;
      await route.fulfill({ json: execution() });
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

  await page.goto("/settings");
  const integrations = page.getByRole("region", { name: "Integrations" });
  await expect(integrations.getByText("Mock Email")).toBeVisible();
  await integrations
    .getByRole("button", { name: "Connect simulation" })
    .click();
  await expect(integrations.getByText("Connected")).toBeVisible();
  expect(connectionCreated).toBe(true);

  await page.goto(`/opportunities/${opportunityId}`);
  const actions = page.getByRole("region", { name: "Next actions" });
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

  await actions.getByRole("button", { name: "Approve action" }).click();
  await expect(actions.getByText(/Nothing was sent or updated/i)).toBeVisible();
  expect(approvalPayload).toEqual({ expectedVersion: 1 });
  await actions.getByRole("tab", { name: "Approved (1)" }).click();
  await expect(
    actions.getByText("Approved — not sent or updated"),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_025A_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025a-actions-desktop.png",
      fullPage: true,
    });
  }
  await actions.getByRole("button", { name: "Preview simulation" }).click();
  await expect(
    actions.getByText("Simulation — no external action will occur"),
  ).toBeVisible();
  await expect(actions.getByText("jordan@example.com")).toBeVisible();
  await expect(
    actions
      .getByRole("definition")
      .filter({ hasText: "Hello Jordan,\n\nThank you for the discussion." }),
  ).toBeVisible();
  await expect(actions.getByRole("textbox")).toHaveCount(0);
  await actions.getByRole("button", { name: "Send email" }).click();
  expect(executionPayload).toEqual({
    previewId: "preview-1",
    connectionId: "connection-1",
    confirmed: true,
  });
  await expect(
    actions.getByText("Simulation in progress", { exact: true }).first(),
  ).toBeVisible();
  await actions
    .getByRole("button", { name: "Refresh simulation status" })
    .click();
  await expect(
    actions.getByText("Simulation complete", { exact: true }).first(),
  ).toBeVisible();
  await expect(actions.getByText(/mock_email_result_1/)).toBeVisible();

  await page.reload();
  const refreshedActions = page.getByRole("region", {
    name: "Next actions",
  });
  await refreshedActions.getByRole("tab", { name: "Approved (1)" }).click();
  await refreshedActions
    .getByRole("button", { name: "Preview simulation" })
    .click();
  await expect(
    refreshedActions.getByText("Simulation history (1)"),
  ).toBeVisible();
  await expect(externalRequests).toEqual([]);
});
