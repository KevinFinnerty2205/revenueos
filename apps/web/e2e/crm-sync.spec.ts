import { expect, test, type Page } from "@playwright/test";

const opportunityId = "opportunity-crm-sync";

const hubspotConnection = {
  id: "hubspot-connection-1",
  connectorKey: "hubspot",
  displayName: "HubSpot",
  connectionStatus: "active",
  supportedCapabilities: [
    "update_opportunity",
    "update_contact",
    "create_activity",
  ],
  capabilityState: ["update_opportunity", "update_contact", "create_activity"],
  createdByUserId: "user-1",
  connectedAt: "2026-08-24T01:00:00Z",
  lastVerifiedAt: "2026-08-24T01:00:00Z",
  revokedAt: null,
  metadataVersion: 1,
  externalAccountId: "1234567",
  externalAccountName: "RevenueOS test account",
  grantedScopes: ["oauth", "crm.objects.deals.read", "crm.objects.deals.write"],
  executionMode: "live",
  simulationOnly: false,
  createdAt: "2026-08-24T01:00:00Z",
  updatedAt: "2026-08-24T01:00:00Z",
};

const hubspotCatalog = {
  connectors: [
    {
      connectorKey: "hubspot",
      displayName: "HubSpot",
      providerFamily: "crm",
      supportedCapabilities: [
        "update_opportunity",
        "update_contact",
        "create_activity",
      ],
      authenticationType: "oauth2_authorisation_code",
      executionRiskClasses: ["data_mutation"],
      configurationSchemaVersion: 1,
      executionMode: "live",
      available: true,
      simulationOnly: false,
    },
  ],
  executionMode: "mixed",
  externalActionsEnabled: true,
};

async function routeShell(page: Page, role: "admin" | "member") {
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
            mockConnectors: false,
            hubspotCrm: true,
          },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
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
        role,
        authMode: "mock",
        requestId: "request-crm-sync-e2e",
      },
    });
  });
}

test("admin connects, maps, verifies and disconnects HubSpot", async ({
  page,
}) => {
  await routeShell(page, "admin");
  let connected = false;
  let amountMapped = false;
  let stageMapped = false;
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["localhost", "127.0.0.1"].includes(url.hostname)) {
      externalRequests.push(request.url());
    }
  });

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
          mockConnectors: false,
          hubspotCrm: true,
          dataExport: false,
          organisationDeletion: false,
        },
        usage: {
          date: "2026-08-24",
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
  await page.route(
    "http://localhost:8000/api/v1/methodologies",
    async (route) => {
      await route.fulfill({
        json: {
          standards: [],
          custom: [],
          current: {
            selection: "none",
            customDefinitionId: null,
            effectiveDefinition: null,
            updatedAt: null,
          },
          customMethodologyLimit: 5,
          fieldLimit: 20,
          executableRulesSupported: false,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations",
    async (route) => {
      await route.fulfill({ json: hubspotCatalog });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections",
    async (route) => {
      await route.fulfill({
        json: {
          items: connected ? [hubspotConnection] : [],
          total: connected ? 1 : 0,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/hubspot/oauth/start",
    async (route) => {
      await route.fulfill({
        json: {
          authorisationUrl:
            "http://localhost:3000/settings/integrations/hubspot/callback?code=fixture-code&state=fixture-state",
          expiresAt: "2026-08-24T01:10:00Z",
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/hubspot/oauth/callback",
    async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        state: "fixture-state",
        code: "fixture-code",
        providerError: null,
      });
      connected = true;
      await route.fulfill({ json: hubspotConnection });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/fields/opportunity",
    async (route) => {
      await route.fulfill({
        json: {
          properties: [
            {
              entityType: "opportunity",
              externalPropertyName: "amount",
              label: "Amount",
              propertyType: "number",
              options: [],
              readOnly: false,
            },
          ],
          mappings: amountMapped
            ? [
                {
                  id: "field-mapping-1",
                  connectionId: "hubspot-connection-1",
                  entityType: "opportunity",
                  revenueosField: "estimated_value",
                  externalPropertyName: "amount",
                  externalPropertyType: "number",
                  authority: "review_before_sync",
                  enabled: true,
                },
              ]
            : [],
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/fields/contact",
    async (route) => {
      await route.fulfill({ json: { properties: [], mappings: [] } });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/fields",
    async (route) => {
      const body = route.request().postDataJSON();
      expect(body).toMatchObject({
        entityType: "opportunity",
        revenueosField: "estimated_value",
        externalPropertyName: "amount",
        authority: "review_before_sync",
      });
      amountMapped = true;
      await route.fulfill({ json: { id: "field-mapping-1", ...body } });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/stages",
    async (route) => {
      if (route.request().method() === "PUT") {
        stageMapped = true;
        await route.fulfill({ json: route.request().postDataJSON() });
        return;
      }
      await route.fulfill({
        json: {
          availableStages: [
            {
              pipelineId: "default",
              pipelineLabel: "Sales pipeline",
              stageId: "qualified",
              stageLabel: "Qualified",
            },
          ],
          mappings: stageMapped
            ? [
                {
                  revenueosStage: "qualification",
                  externalPipelineId: "default",
                  externalStageId: "qualified",
                },
              ]
            : [],
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/test",
    async (route) => route.fulfill({ json: hubspotConnection }),
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1",
    async (route) => {
      expect(route.request().method()).toBe("DELETE");
      connected = false;
      await route.fulfill({ status: 204, body: "" });
    },
  );

  await page.goto("/settings");
  const integrations = page.getByRole("region", { name: "Integrations" });
  await integrations.getByRole("button", { name: "Connect HubSpot" }).click();
  await expect(page.getByRole("heading", { name: "Connected" })).toBeVisible();
  await expect(
    page.getByText(/RevenueOS test account is connected/i),
  ).toBeVisible();
  await page.getByRole("link", { name: "Return to settings" }).click();

  await expect(
    integrations.getByText("Live — explicit review required"),
  ).toBeVisible();
  await expect(integrations.getByText(/RevenueOS test account/)).toBeVisible();
  await integrations.getByText("Advanced mapping settings").click();
  await integrations
    .getByRole("button", { name: "Load HubSpot fields and stages" })
    .click();
  await integrations
    .getByRole("combobox", { name: "Estimated Value" })
    .selectOption("amount");
  await expect(
    integrations.getByText(/field authority and mapping saved/i),
  ).toBeVisible();
  await integrations
    .getByRole("combobox", { name: "Qualification" })
    .selectOption("default::qualified");
  await expect(integrations.getByText(/stage mapping saved/i)).toBeVisible();
  await integrations.getByRole("button", { name: "Test connection" }).click();
  await expect(
    integrations.getByText(/authorisation and account identity were verified/i),
  ).toBeVisible();

  if (process.env.CAPTURE_WO_025C_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025c-hubspot-settings.png",
      fullPage: true,
    });
  }

  await integrations.getByRole("button", { name: "Disconnect" }).click();
  await expect(integrations.getByText("Not connected")).toBeVisible();
  await expect(
    integrations.getByText(/Provider revocation was attempted/i),
  ).toBeVisible();
  expect(externalRequests).toEqual([]);
});

function crmAction(status: "proposed" | "approved") {
  return {
    id: "crm-action-1",
    organisationId: "organisation-1",
    opportunityId,
    interactionId: "interaction-1",
    actionType: "update_opportunity",
    status,
    priority: "high",
    audience: "internal",
    riskClass: "data_mutation",
    currentVersion: 1,
    approvedVersion: status === "approved" ? 1 : null,
    title: "Review opportunity amount update",
    description: "Apply the reviewed commercial value to the linked CRM deal.",
    proposedDueAt: null,
    targetEntityType: "opportunity",
    targetEntityId: opportunityId,
    proposedPayload: {
      kind: "update_opportunity",
      field: "estimated_value",
      currentValue: "125000.50",
      proposedValue: "140000.00",
      reason: "The reviewed scope changed.",
    },
    sourceRefs: [
      {
        sourceType: "ai_artifact",
        sourceId: "artifact-1",
        itemKey: "next_best_action",
        label: "Final validated Next Best Action",
        origin: "validated_intelligence",
      },
    ],
    provenanceSummary: "Derived from final validated Interaction Intelligence.",
    generatedAt: "2026-08-24T01:00:00Z",
    versionCreatedAt: "2026-08-24T01:00:00Z",
    createdByUserId: "user-1",
    reviewedByUserId: status === "approved" ? "user-1" : null,
    reviewedAt: status === "approved" ? "2026-08-24T01:01:00Z" : null,
    approvedAt: status === "approved" ? "2026-08-24T01:01:00Z" : null,
    rejectedAt: null,
    rejectionReasonCode: null,
    supersedesActionId: null,
    completedByUserId: null,
    completedAt: null,
    executionState: "not_executed",
    sendReady: false,
  };
}

test("salesperson links and confirms an exact CRM update after stale-state review", async ({
  page,
}) => {
  await routeShell(page, "member");
  let actionStatus: "proposed" | "approved" = "proposed";
  let previewCount = 0;
  let executeCount = 0;
  let executionComplete = false;
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["localhost", "127.0.0.1"].includes(url.hostname)) {
      externalRequests.push(request.url());
    }
  });

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
            estimatedValue: "125000.50",
            currency: "AUD",
            expectedCloseDate: "2026-09-30",
            ownerUserId: "user-1",
            ownerName: "Alex Morgan",
            description:
              "Canonical RevenueOS value remains unchanged by CRM sync.",
            createdAt: "2026-08-01T00:00:00Z",
            updatedAt: "2026-08-24T00:00:00Z",
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
          generatedAt: "2026-08-24T00:00:00Z",
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
      await route.fulfill({
        json: { items: [crmAction(actionStatus)], total: 1 },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/actions/crm-action-1/approve",
    async (route) => {
      expect(route.request().postDataJSON()).toEqual({ expectedVersion: 1 });
      actionStatus = "approved";
      await route.fulfill({ json: crmAction("approved") });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections",
    async (route) => {
      await route.fulfill({ json: { items: [hubspotConnection], total: 1 } });
    },
  );
  await page.route(
    `http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/entities/opportunity/${opportunityId}`,
    async (route) => {
      await route.fulfill({
        json: {
          id: "entity-mapping-1",
          connectionId: "hubspot-connection-1",
          connectorKey: "hubspot",
          revenueosEntityType: "opportunity",
          revenueosEntityId: opportunityId,
          externalObjectType: "deal",
          externalObjectId: "deal-1",
          externalUpdatedAt: "2026-08-24T01:01:00Z",
          lastSyncedAt: null,
          syncState: "active",
          createdAt: "2026-08-24T01:00:00Z",
          updatedAt: "2026-08-24T01:00:00Z",
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/actions/crm-action-1/execution-options",
    async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              connectionId: "hubspot-connection-1",
              connectorKey: "hubspot",
              connectorDisplayName: "HubSpot",
              capability: "update_opportunity",
              riskClass: "data_mutation",
              executionMode: "live",
              simulationOnly: false,
            },
          ],
          total: 1,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/actions/crm-action-1/execution-preview",
    async (route) => {
      previewCount += 1;
      const currentValue = previewCount === 1 ? "125000.50" : "130000.00";
      await route.fulfill({
        json: {
          id: `preview-${previewCount}`,
          actionProposalId: "crm-action-1",
          actionVersion: 1,
          connectionId: "hubspot-connection-1",
          connectorKey: "hubspot",
          connectorDisplayName: "HubSpot",
          capability: "update_opportunity",
          riskClass: "data_mutation",
          executionMode: "live",
          simulationOnly: false,
          readiness: "ready",
          summary:
            "Apply this reviewed field update to the linked HubSpot deal.",
          confirmationLabel: "Update CRM",
          previewFingerprint: "f".repeat(64),
          content: {
            kind: "crm",
            targetType: "opportunity",
            targetId: opportunityId,
            field: "estimated_value",
            currentExternalValue: currentValue,
            expectedExternalValue: currentValue,
            newValue: "140000.00",
            fieldAuthority: "review_before_sync",
            externalUpdatedAt: "2026-08-24T01:01:00Z",
            action: "update_opportunity",
          },
          expiresAt: "2026-08-24T01:12:00Z",
          createdAt: "2026-08-24T01:02:00Z",
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/actions/crm-action-1/executions",
    async (route) => {
      await route.fulfill({ json: { items: [], total: 0 } });
    },
  );
  const execution = () => ({
    id: "execution-live-1",
    actionProposalId: "crm-action-1",
    actionVersion: 1,
    connectionId: "hubspot-connection-1",
    connectorKey: "hubspot",
    connectorDisplayName: "HubSpot",
    capability: "update_opportunity",
    riskClass: "data_mutation",
    executionStatus: executionComplete ? "succeeded" : "queued",
    executionMode: "live",
    simulationOnly: false,
    confirmedByUserId: "user-1",
    confirmedAt: "2026-08-24T01:02:00Z",
    startedAt: executionComplete ? "2026-08-24T01:02:01Z" : null,
    completedAt: executionComplete ? "2026-08-24T01:02:02Z" : null,
    failedAt: null,
    safeFailureCode: null,
    externalResultId: executionComplete ? "deal-1" : null,
    attemptCount: executionComplete ? 1 : 0,
    retryable: false,
    safeMessage: executionComplete
      ? "HubSpot contains the approved value."
      : "The reviewed HubSpot update is queued.",
    createdAt: "2026-08-24T01:02:00Z",
    updatedAt: "2026-08-24T01:02:02Z",
  });
  await page.route(
    "http://localhost:8000/api/v1/actions/crm-action-1/execute",
    async (route) => {
      executeCount += 1;
      if (executeCount === 1) {
        await route.fulfill({
          status: 409,
          json: {
            code: "stale_external_state",
            message:
              "HubSpot changed after this preview. Review the current value before trying again.",
            requestId: "request-stale-state",
          },
        });
        return;
      }
      expect(route.request().postDataJSON()).toEqual({
        previewId: "preview-2",
        connectionId: "hubspot-connection-1",
        confirmed: true,
      });
      await route.fulfill({ status: 202, json: execution() });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/executions/execution-live-1",
    async (route) => {
      executionComplete = true;
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

  await page.goto(`/opportunities/${opportunityId}`);
  const crmLink = page.getByRole("region", { name: "CRM record link" });
  await crmLink.getByRole("button", { name: "Connect to CRM record" }).click();
  await expect(crmLink.getByText("HubSpot deal ID: deal-1")).toBeVisible();

  const actions = page.getByRole("region", { name: "Next actions" });
  await actions.getByRole("button", { name: "Approve action" }).click();
  await expect(actions.getByText(/Nothing was sent or updated/i)).toBeVisible();
  await actions.getByRole("tab", { name: "Approved (1)" }).click();
  await actions.getByRole("button", { name: "Review execution" }).click();
  await expect(actions.getByText("125000.50")).toBeVisible();
  await expect(actions.getByText("140000.00")).toBeVisible();
  await expect(actions.getByText("Review Before Sync")).toBeVisible();

  if (process.env.CAPTURE_WO_025C_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025c-crm-preview.png",
      fullPage: true,
    });
  }

  await actions.getByRole("button", { name: "Update CRM" }).click();
  await expect(actions.getByRole("alert")).toContainText(
    "HubSpot changed after this preview",
  );
  await actions.getByRole("button", { name: "Cancel" }).click();
  await actions.getByRole("button", { name: "Review execution" }).click();
  await expect(actions.getByText("130000.00")).toBeVisible();
  await actions.getByRole("button", { name: "Update CRM" }).click();
  await expect(
    actions.getByText("HubSpot action in progress", { exact: true }),
  ).toBeVisible();
  await actions
    .getByRole("button", { name: "Refresh execution status" })
    .click();
  await expect(
    actions.getByText("HubSpot update complete", { exact: true }),
  ).toBeVisible();
  await expect(actions.getByText(/HubSpot result ID: deal-1/)).toBeVisible();
  await expect(page.getByText(/125,000\.50/).first()).toBeVisible();
  expect(externalRequests).toEqual([]);
});
