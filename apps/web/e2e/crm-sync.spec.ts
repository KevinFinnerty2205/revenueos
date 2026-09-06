import { expect, test, type Page } from "@playwright/test";

const opportunityId = "opportunity-crm-sync";
const webOrigin = `http://localhost:${process.env.PLAYWRIGHT_PORT ?? "3000"}`;

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

const salesforceConnection = {
  ...hubspotConnection,
  id: "salesforce-connection-1",
  connectorKey: "salesforce",
  displayName: "Salesforce",
  supportedCapabilities: [
    "sync_accounts",
    "sync_contacts",
    "sync_opportunities",
    "create_account",
    "create_contact",
    "create_opportunity",
    "update_account",
    "update_contact",
    "update_opportunity",
  ],
  capabilityState: [
    "sync_accounts",
    "sync_contacts",
    "sync_opportunities",
    "create_account",
    "create_contact",
    "create_opportunity",
    "update_account",
    "update_contact",
    "update_opportunity",
  ],
  externalAccountId: "005000000000001",
  externalAccountName: "Oryntela synthetic developer org",
  externalTenantId: "00D000000000001",
  grantedScopes: ["api", "openid", "refresh_token"],
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
    {
      connectorKey: "salesforce",
      displayName: "Salesforce",
      providerFamily: "crm",
      supportedCapabilities: [
        "sync_accounts",
        "sync_contacts",
        "sync_opportunities",
        "create_account",
        "create_contact",
        "create_opportunity",
        "update_account",
        "update_contact",
        "update_opportunity",
      ],
      authenticationType: "oauth2_authorisation_code_pkce",
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
  let connectedProvider: "hubspot" | "salesforce" | null = null;
  let salesforceNeedsReauth = false;
  let amountMapped = false;
  let stageMapped = false;
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["localhost", "127.0.0.1"].includes(url.hostname)) {
      externalRequests.push(request.url());
    }
  });
  await page.route(
    "http://localhost:8000/api/v1/crm/availability",
    async (route) => {
      await route.fulfill({
        json: {
          moduleKey: "crm",
          state: "available",
          enabled: true,
          canManage: true,
          mode: connectedProvider ? "external" : "native",
          externalProvider: connectedProvider,
          externalConnected: connectedProvider !== null,
          customFieldsReadOnly: connectedProvider !== null,
          message: connectedProvider
            ? `${connectedProvider === "hubspot" ? "HubSpot" : "Salesforce"} controls mapped CRM fields. Oryntela intelligence remains separate.`
            : "Oryntela Native CRM is ready.",
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/crm/custom-fields",
    async (route) => route.fulfill({ json: [] }),
  );
  await page.route("http://localhost:8000/api/v1/pipelines", async (route) =>
    route.fulfill({ json: [] }),
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
          items:
            connectedProvider === "hubspot"
              ? [hubspotConnection]
              : connectedProvider === "salesforce"
                ? [
                    {
                      ...salesforceConnection,
                      connectionStatus: salesforceNeedsReauth
                        ? "reauthorisation_required"
                        : "active",
                    },
                  ]
                : [],
          total: connectedProvider ? 1 : 0,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/hubspot/oauth/start",
    async (route) => {
      await route.fulfill({
        json: {
          authorisationUrl: `${webOrigin}/settings/integrations/hubspot/callback?code=fixture-code&state=fixture-state`,
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
      connectedProvider = "hubspot";
      await route.fulfill({ json: hubspotConnection });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/fields/company",
    async (route) => {
      await route.fulfill({ json: { properties: [], mappings: [] } });
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
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/status",
    async (route) => {
      await route.fulfill({
        json: {
          connectionId: hubspotConnection.id,
          providerKey: "hubspot",
          lifecycle: "initial_sync",
          healthStatus: "healthy",
          connectorEnabled: true,
          writebackEnabled: false,
          mappingVersion: 3,
          recordsSeen: 148,
          recordsApplied: 145,
          conflictCount: 1,
          initialSyncStartedAt: "2026-08-24T01:00:00Z",
          initialSyncCompletedAt: "2026-08-24T01:03:00Z",
          lastSuccessfulSyncAt: null,
          lastHealthCheckedAt: "2026-08-24T01:03:00Z",
          lastSafeErrorCode: null,
          cursors: [],
          latestJob: {
            id: "hubspot-initial-job",
            mode: "initial",
            status: "running",
            attemptCount: 0,
            startedAt: "2026-08-24T01:00:00Z",
            completedAt: null,
            safeFailureCode: null,
          },
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/owners",
    async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              id: "owner-map-1",
              externalOwnerId: "hubspot-owner-1",
              externalOwnerName: "Alex Morgan",
              externalOwnerEmail: "alex@example.test",
              userId: "user-1",
              state: "mapped",
            },
          ],
          total: 1,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/crm/members",
    async (route) => {
      await route.fulfill({
        json: [
          {
            userId: "user-1",
            displayName: "Alex Morgan",
            email: "alex@example.test",
            active: true,
          },
        ],
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/hubspot-connection-1/crm/conflicts",
    async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              id: "conflict-1",
              connectionId: hubspotConnection.id,
              objectType: "opportunity",
              externalObjectId: "deal-1",
              revenueosEntityId: opportunityId,
              fieldKey: "stage",
              oryntelaValue: "Discovery",
              providerValue: "Contract sent",
              status: "open",
              resolution: null,
              detectedAt: "2026-08-24T01:03:00Z",
              resolvedAt: null,
            },
          ],
          total: 1,
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
      connectedProvider = null;
      await route.fulfill({ status: 204, body: "" });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/salesforce/oauth/start",
    async (route) => {
      if (connectedProvider !== null) {
        await route.fulfill({
          status: 409,
          json: {
            code: "crm_provider_switch_required",
            message:
              "Disconnect the active CRM and review the provider switch before connecting Salesforce.",
            requestId: "request-crm-switch",
          },
        });
        return;
      }
      await route.fulfill({
        json: {
          authorisationUrl: `${webOrigin}/settings/integrations/salesforce/callback?code=salesforce-code&state=salesforce-state`,
          expiresAt: "2026-08-24T01:10:00Z",
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/salesforce/oauth/callback",
    async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        state: "salesforce-state",
        code: "salesforce-code",
        providerError: null,
      });
      connectedProvider = "salesforce";
      await route.fulfill({ json: salesforceConnection });
    },
  );
  const salesforceFields = {
    company: {
      properties: [
        {
          entityType: "company",
          externalPropertyName: "Name",
          label: "Account name",
          propertyType: "string",
          options: [],
          readOnly: false,
        },
      ],
      mappings: [
        {
          id: "sf-account-name",
          connectionId: salesforceConnection.id,
          entityType: "company",
          revenueosField: "name",
          externalPropertyName: "Name",
          externalPropertyType: "string",
          authority: "crm_authoritative",
          enabled: true,
        },
      ],
    },
    contact: {
      properties: [
        {
          entityType: "contact",
          externalPropertyName: "Email",
          label: "Email",
          propertyType: "email",
          options: [],
          readOnly: false,
        },
      ],
      mappings: [
        {
          id: "sf-contact-email",
          connectionId: salesforceConnection.id,
          entityType: "contact",
          revenueosField: "email",
          externalPropertyName: "Email",
          externalPropertyType: "email",
          authority: "crm_authoritative",
          enabled: true,
        },
      ],
    },
    opportunity: {
      properties: [
        {
          entityType: "opportunity",
          externalPropertyName: "StageName",
          label: "Stage",
          propertyType: "enumeration",
          options: [{ value: "Proposal/Price Quote", label: "Proposal" }],
          readOnly: false,
        },
      ],
      mappings: [
        {
          id: "sf-opportunity-stage",
          connectionId: salesforceConnection.id,
          entityType: "opportunity",
          revenueosField: "stage",
          externalPropertyName: "StageName",
          externalPropertyType: "enumeration",
          authority: "crm_authoritative",
          enabled: true,
        },
      ],
    },
  };
  for (const entityType of ["company", "contact", "opportunity"] as const) {
    await page.route(
      `http://localhost:8000/api/v1/integrations/connections/salesforce-connection-1/crm/fields/${entityType}`,
      async (route) => route.fulfill({ json: salesforceFields[entityType] }),
    );
  }
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/salesforce-connection-1/crm/stages",
    async (route) => {
      await route.fulfill({
        json: {
          availableStages: [
            {
              pipelineId: "standard",
              pipelineLabel: "Salesforce pipeline",
              stageId: "Proposal/Price Quote",
              stageLabel: "Proposal",
            },
          ],
          mappings: [
            {
              revenueosStage: "proposal",
              externalPipelineId: "standard",
              externalStageId: "Proposal/Price Quote",
            },
          ],
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/salesforce-connection-1/crm/status",
    async (route) => {
      await route.fulfill({
        json: {
          connectionId: salesforceConnection.id,
          providerKey: "salesforce",
          lifecycle: "needs_attention",
          healthStatus: "degraded",
          connectorEnabled: true,
          writebackEnabled: false,
          mappingVersion: 4,
          recordsSeen: 620,
          recordsApplied: 618,
          conflictCount: 1,
          initialSyncStartedAt: "2026-08-24T02:00:00Z",
          initialSyncCompletedAt: "2026-08-24T02:09:00Z",
          lastSuccessfulSyncAt: "2026-08-24T02:09:00Z",
          lastHealthCheckedAt: "2026-08-24T02:09:00Z",
          lastSafeErrorCode: "mapping_review_required",
          cursors: [],
          latestJob: null,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/salesforce-connection-1/crm/owners",
    async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              id: "sf-owner-map-1",
              externalOwnerId: "005000000000002",
              externalOwnerName: "Taylor Chen",
              externalOwnerEmail: "taylor@example.test",
              userId: null,
              state: "unmapped",
            },
          ],
          total: 1,
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/integrations/connections/salesforce-connection-1/crm/conflicts",
    async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              id: "sf-conflict-1",
              connectionId: salesforceConnection.id,
              objectType: "opportunity",
              externalObjectId: "006000000000001",
              revenueosEntityId: opportunityId,
              fieldKey: "stage",
              oryntelaValue: "Evaluation",
              providerValue: "Proposal/Price Quote",
              status: "open",
              resolution: null,
              detectedAt: "2026-08-24T02:09:00Z",
              resolvedAt: null,
            },
          ],
          total: 1,
        },
      });
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
    integrations.getByText("Live — explicit review required").first(),
  ).toBeVisible();
  await expect(integrations.getByText(/RevenueOS test account/)).toBeVisible();
  await integrations.getByText("CRM sync, ownership and mappings").click();
  await integrations
    .getByRole("button", { name: "Load HubSpot configuration" })
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
  if (process.env.CAPTURE_WO_042_SCREENSHOTS === "1") {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await integrations.screenshot({
      path: "../../docs/07-sprints/assets/wo-042/hubspot-settings-desktop.png",
    });
    await page.getByRole("region", { name: "CRM foundation" }).screenshot({
      path: "../../docs/07-sprints/assets/wo-042/native-crm-choice-desktop.png",
    });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    await integrations.screenshot({
      path: "../../docs/07-sprints/assets/wo-042/hubspot-settings-mobile.png",
    });
    await page.getByRole("region", { name: "CRM foundation" }).screenshot({
      path: "../../docs/07-sprints/assets/wo-042/native-crm-choice-mobile.png",
    });
  }

  await integrations
    .getByRole("button", { name: "Connect Salesforce" })
    .click();
  await expect(
    integrations.getByText(
      /Disconnect the active CRM and review the provider switch/i,
    ),
  ).toBeVisible();

  await integrations.getByRole("button", { name: "Disconnect" }).click();
  await integrations
    .getByRole("button", { name: "Confirm disconnect" })
    .click();
  await expect(integrations.getByText("Not connected").first()).toBeVisible();
  await expect(
    integrations.getByText(/Provider revocation was attempted/i),
  ).toBeVisible();

  await integrations
    .getByRole("button", { name: "Connect Salesforce" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Connected read-only" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Oryntela synthetic developer org is connected/i),
  ).toBeVisible();
  await page.getByRole("link", { name: "Return to settings" }).click();
  await expect(
    integrations.getByText(/Oryntela synthetic developer org/),
  ).toBeVisible();
  await integrations.getByText("CRM sync, ownership and mappings").click();
  await integrations
    .getByRole("button", { name: "Load Salesforce configuration" })
    .click();
  await expect(integrations.getByText("Needs attention")).toBeVisible();
  await expect(integrations.getByText("Taylor Chen")).toBeVisible();
  await expect(
    integrations.getByRole("button", {
      name: "Use reviewed Salesforce value",
    }),
  ).toBeVisible();

  if (process.env.CAPTURE_WO_042_SCREENSHOTS === "1") {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await integrations.screenshot({
      path: "../../docs/07-sprints/assets/wo-042/salesforce-settings-desktop.png",
    });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    await integrations.screenshot({
      path: "../../docs/07-sprints/assets/wo-042/salesforce-settings-mobile.png",
    });
  }

  salesforceNeedsReauth = true;
  await page.reload();
  await expect(integrations.getByText("Reconnect required")).toBeVisible();
  await expect(
    integrations.getByRole("button", { name: "Reconnect" }),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_042_SCREENSHOTS === "1") {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await integrations.screenshot({
      path: "../../docs/07-sprints/assets/wo-042/salesforce-reauthorisation-desktop.png",
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await integrations.screenshot({
      path: "../../docs/07-sprints/assets/wo-042/salesforce-reauthorisation-mobile.png",
    });
  }
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
  await expect(
    crmLink.getByText("HubSpot opportunity ID: deal-1"),
  ).toBeVisible();

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
