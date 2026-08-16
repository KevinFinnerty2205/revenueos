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
});
