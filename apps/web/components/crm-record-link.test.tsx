import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CRMRecordLink } from "@/components/crm-record-link";

function response(body: object | null) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const connection = {
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
  externalAccountId: "1234567",
  externalAccountName: "RevenueOS test account",
  grantedScopes: ["oauth"],
  metadataVersion: 1,
  executionMode: "live",
  simulationOnly: false,
  createdAt: "2026-08-24T01:00:00Z",
  updatedAt: "2026-08-24T01:00:00Z",
};

describe("CRMRecordLink", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("does not fetch on opportunity load and links only an explicitly selected result", async () => {
    const mapping = {
      id: "mapping-1",
      connectionId: connection.id,
      connectorKey: "hubspot",
      revenueosEntityType: "opportunity",
      revenueosEntityId: "opportunity-1",
      externalObjectType: "deal",
      externalObjectId: "deal-42",
      externalUpdatedAt: "2026-08-24T01:00:00Z",
      lastSyncedAt: null,
      syncState: "active",
      createdAt: "2026-08-24T01:00:00Z",
      updatedAt: "2026-08-24T01:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ items: [connection], total: 1 }))
      .mockResolvedValueOnce(response(null))
      .mockResolvedValueOnce(
        response({
          items: [
            {
              externalObjectType: "deal",
              externalObjectId: "deal-42",
              displayName: "Qantas Expansion",
              secondaryLabel: "Technical validation",
              updatedAt: "2026-08-24T01:00:00Z",
            },
          ],
          total: 1,
        }),
      )
      .mockResolvedValueOnce(response(mapping));
    vi.stubGlobal("fetch", fetchMock);

    render(<CRMRecordLink opportunityId="opportunity-1" />);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Connect to CRM record" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    fireEvent.change(screen.getByLabelText("Search HubSpot deals"), {
      target: { value: "Qantas" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Qantas Expansion")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Link" }));
    expect(await screen.findByText("HubSpot deal ID: deal-42")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body))).toEqual({
      connectionId: connection.id,
      externalObjectType: "deal",
      externalObjectId: "deal-42",
    });
  });
});
