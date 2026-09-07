import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IntegrationSettings } from "@/components/integration-settings";

function response(body: object) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const catalog = {
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
};

const connection = {
  id: "connection-1",
  connectorKey: "mock_email",
  displayName: "Mock Email",
  connectionStatus: "active",
  supportedCapabilities: ["send_email"],
  capabilityState: ["send_email"],
  createdByUserId: "user-1",
  connectedAt: "2026-08-15T01:00:00Z",
  lastVerifiedAt: "2026-08-15T01:00:00Z",
  revokedAt: null,
  metadataVersion: 1,
  executionMode: "simulation",
  simulationOnly: true,
  createdAt: "2026-08-15T01:00:00Z",
  updatedAt: "2026-08-15T01:00:00Z",
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

const hubspotConnection = {
  ...connection,
  id: "hubspot-connection-1",
  connectorKey: "hubspot",
  displayName: "HubSpot",
  supportedCapabilities: [
    "update_opportunity",
    "update_contact",
    "create_activity",
  ],
  capabilityState: ["update_opportunity", "update_contact", "create_activity"],
  externalAccountId: "1234567",
  externalAccountName: "RevenueOS test account",
  grantedScopes: ["oauth", "crm.objects.deals.read"],
  executionMode: "live",
  simulationOnly: false,
};

const microsoftCatalog = {
  connectors: [
    {
      connectorKey: "microsoft_365",
      displayName: "Microsoft 365",
      providerFamily: "mailbox_calendar",
      supportedCapabilities: ["send_email", "reconcile_email", "read_calendar"],
      authenticationType: "oauth2_authorisation_code",
      executionRiskClasses: ["external_customer_facing"],
      configurationSchemaVersion: 1,
      executionMode: "live",
      available: true,
      simulationOnly: false,
    },
  ],
  executionMode: "live",
  externalActionsEnabled: true,
};

const microsoftConnection = {
  ...connection,
  id: "microsoft-connection-1",
  connectorKey: "microsoft_365",
  displayName: "Microsoft 365",
  connectionStatus: "reauthorisation_required",
  supportedCapabilities: ["send_email", "reconcile_email", "read_calendar"],
  capabilityState: ["send_email", "reconcile_email", "read_calendar"],
  externalAccountId: "microsoft-user-1",
  externalAccountName: "Alex Morgan",
  externalAccountEmail: "alex@example.test",
  externalTenantId: "11111111-2222-4333-8444-555555555555",
  grantedScopes: ["Mail.Send", "Mail.Read", "Calendars.ReadBasic"],
  executionMode: "live",
  simulationOnly: false,
};

const googleCatalog = {
  connectors: [
    {
      connectorKey: "google_workspace",
      displayName: "Google Workspace",
      providerFamily: "mailbox_calendar",
      supportedCapabilities: ["send_email", "reconcile_email", "read_calendar"],
      authenticationType: "oauth2_authorisation_code",
      executionRiskClasses: ["external_customer_facing"],
      configurationSchemaVersion: 1,
      executionMode: "live",
      available: true,
      simulationOnly: false,
    },
  ],
  executionMode: "live",
  externalActionsEnabled: true,
};

const googleConnection = {
  ...connection,
  id: "google-connection-1",
  connectorKey: "google_workspace",
  displayName: "Google Workspace",
  connectionStatus: "active",
  supportedCapabilities: ["send_email", "reconcile_email", "read_calendar"],
  capabilityState: ["send_email", "reconcile_email", "read_calendar"],
  externalAccountId: "google-user-1",
  externalAccountName: "Alex Morgan",
  externalAccountEmail: "alex@workspace.example",
  externalTenantId: "workspace.example",
  grantedScopes: [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned.readonly",
  ],
  executionMode: "live",
  simulationOnly: false,
};

describe("IntegrationSettings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("labels mock connectors as simulation and lets an admin connect one", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(catalog))
      .mockResolvedValueOnce(response({ items: [], total: 0 }))
      .mockResolvedValueOnce(response(connection))
      .mockResolvedValueOnce(response(catalog))
      .mockResolvedValueOnce(response({ items: [connection], total: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<IntegrationSettings />);
    expect(await screen.findByText("Mock Email")).toBeVisible();
    expect(
      screen.getAllByText(/Simulation — no external action/i).length,
    ).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Connect simulation" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    expect(JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body))).toEqual({
      connectorKey: "mock_email",
    });
    expect(await screen.findByText("Connected")).toBeVisible();
    expect(
      screen.getByText(/cannot contact an external system/i),
    ).toBeVisible();
  });

  it("shows a live HubSpot connection and keeps typed mappings behind disclosure", async () => {
    const accountFields = { properties: [], mappings: [] };
    const opportunityFields = {
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
      mappings: [],
    };
    const contactFields = {
      properties: [
        {
          entityType: "contact",
          externalPropertyName: "firstname",
          label: "First name",
          propertyType: "string",
          options: [],
          readOnly: false,
        },
      ],
      mappings: [],
    };
    const stages = {
      availableStages: [
        {
          pipelineId: "default",
          pipelineLabel: "Sales pipeline",
          stageId: "qualified",
          stageLabel: "Qualified",
        },
      ],
      mappings: [],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(hubspotCatalog))
      .mockResolvedValueOnce(response({ items: [hubspotConnection], total: 1 }))
      .mockResolvedValueOnce(response(accountFields))
      .mockResolvedValueOnce(response(opportunityFields))
      .mockResolvedValueOnce(response(contactFields))
      .mockResolvedValueOnce(response(stages))
      .mockResolvedValueOnce(
        response({
          connectionId: hubspotConnection.id,
          providerKey: "hubspot",
          lifecycle: "mapping_required",
          healthStatus: "healthy",
          connectorEnabled: true,
          writebackEnabled: false,
          mappingVersion: 1,
          recordsSeen: 3,
          recordsApplied: 3,
          conflictCount: 0,
          initialSyncStartedAt: "2026-08-15T01:00:00Z",
          initialSyncCompletedAt: "2026-08-15T01:01:00Z",
          lastSuccessfulSyncAt: "2026-08-15T01:01:00Z",
          lastHealthCheckedAt: "2026-08-15T01:01:00Z",
          lastSafeErrorCode: null,
          cursors: [],
          latestJob: null,
        }),
      )
      .mockResolvedValueOnce(response({ items: [], total: 0 }))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response({ items: [], total: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<IntegrationSettings />);
    expect(
      await screen.findByText("Live — explicit review required"),
    ).toBeVisible();
    expect(screen.getByText(/RevenueOS test account/)).toBeVisible();
    expect(screen.getByText(/never sends a raw transcript/i)).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: "Estimated Value" }),
    ).toBeNull();

    fireEvent.click(screen.getByText("CRM sync, ownership and mappings"));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Load HubSpot configuration",
      }),
    );
    expect(
      await screen.findByRole("combobox", { name: "Estimated Value" }),
    ).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Currency" })).toBeVisible();
    expect(
      screen.getAllByRole("combobox", { name: "Name" }).length,
    ).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("combobox", { name: "Phone" })).toBeVisible();
    expect(
      screen
        .getAllByRole("combobox", { name: "Field authority" })
        .every((item) => item.hasAttribute("disabled")),
    ).toBe(true);
    expect(
      screen.getAllByText("Sales pipeline — Qualified").length,
    ).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledTimes(10);
  });

  it("explains Microsoft access and shows reauthorisation without provider internals", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(microsoftCatalog))
      .mockResolvedValueOnce(
        response({ items: [microsoftConnection], total: 1 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: "connection_reauthorisation_required",
            message: "Microsoft 365 needs to be reconnected.",
            requestId: "synthetic-request",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<IntegrationSettings />);
    expect(
      (await screen.findAllByText("Reconnect required")).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("alex@example.test")).toBeVisible();
    expect(screen.getByText("Email: Reconnect required")).toBeVisible();
    expect(screen.getByText("Calendar: Reconnect required")).toBeVisible();
    expect(screen.queryByText(/11111111-2222/)).toBeNull();
    expect(screen.queryByText(/Mail\.Read/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Reconnect" }));
    const permissionGroup = screen.getByRole("dialog", {
      name: "Before you continue",
    });
    expect(permissionGroup).toBeVisible();
    expect(screen.getByText(/reviewed and approved/i)).toBeVisible();
    expect(
      screen.getByText(/Microsoft grants mail read access/i),
    ).toBeVisible();
    expect(
      screen.getByText(/Unrelated mail content is not read or stored/i),
    ).toBeVisible();
    expect(screen.getByText(/Event bodies and attachments/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reconnect" })).toHaveFocus(),
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("explains restricted Google reply access and exposes mailbox sync health", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(googleCatalog))
      .mockResolvedValueOnce(response({ items: [googleConnection], total: 1 }))
      .mockResolvedValueOnce(
        response({
          connectionId: "google-connection-1",
          lastSuccessfulSyncAt: "2026-09-06T01:00:00Z",
          lastErrorCategory: null,
          state: "healthy",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<IntegrationSettings />);
    expect(await screen.findByText("alex@workspace.example")).toBeVisible();
    expect(screen.getByText("Replies: Connected")).toBeVisible();
    await waitFor(() =>
      expect(screen.getByText(/Last sync:/)).toHaveTextContent("06/09/2026"),
    );

    const reconnect = screen.getByRole("button", { name: "Reconnect" });
    fireEvent.click(reconnect);
    const permissionDialog = screen.getByRole("dialog", {
      name: "Before you continue",
    });
    expect(permissionDialog).toBeVisible();
    expect(
      screen.getByText(/Google grants restricted Gmail read-only access/i),
    ).toBeVisible();
    expect(
      screen.getByText(
        /scans a bounded window of Inbox and Sent message metadata/i,
      ),
    ).toBeVisible();
    expect(screen.getByText(/your primary work calendar/i)).toBeVisible();
    expect(screen.queryByText(/gmail\.readonly/i)).toBeNull();
    await waitFor(() =>
      expect(screen.getByText("Before you continue")).toHaveFocus(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(reconnect).toHaveFocus());
  });

  it("returns keyboard focus after cancelling Microsoft disconnect", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(microsoftCatalog))
      .mockResolvedValueOnce(
        response({
          items: [{ ...microsoftConnection, connectionStatus: "active" }],
          total: 1,
        }),
      )
      .mockResolvedValueOnce(
        response({
          connectionId: "microsoft-connection-1",
          lastSuccessfulSyncAt: "2026-09-06T01:00:00Z",
          lastErrorCategory: null,
          state: "healthy",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<IntegrationSettings />);
    const reconnect = await screen.findByRole("button", {
      name: "Reconnect",
    });
    fireEvent.click(reconnect);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(reconnect).toHaveFocus());
    const disconnect = await screen.findByRole("button", {
      name: "Disconnect",
    });
    fireEvent.click(disconnect);
    expect(
      screen.getByRole("dialog", { name: "Disconnect Microsoft 365?" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Keep connected" }));
    await waitFor(() => expect(disconnect).toHaveFocus());
  });
});
