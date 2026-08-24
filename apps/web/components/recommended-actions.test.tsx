import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ActionProposal } from "@revenueos/shared";
import { RecommendedActions } from "@/components/recommended-actions";

function response(body: object) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function action(overrides: Partial<ActionProposal> = {}): ActionProposal {
  return {
    id: "action-1",
    organisationId: "organisation-1",
    opportunityId: "opportunity-1",
    interactionId: "interaction-1",
    actionType: "follow_up_email",
    status: "proposed",
    priority: "high",
    audience: "customer_facing",
    riskClass: "external_customer_facing",
    currentVersion: 1,
    approvedVersion: null,
    title: "Send the reviewed follow-up draft",
    description:
      "Review the final draft before taking any action outside RevenueOS.",
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
    reviewedByUserId: null,
    reviewedAt: null,
    approvedAt: null,
    rejectedAt: null,
    rejectionReasonCode: null,
    supersedesActionId: null,
    completedByUserId: null,
    completedAt: null,
    executionState: "not_executed",
    sendReady: false,
    ...overrides,
  };
}

describe("RecommendedActions", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("labels customer-facing proposals and records approval without execution controls", async () => {
    const approved = action({
      status: "approved",
      approvedVersion: 1,
      approvedAt: "2026-08-15T03:00:00Z",
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(approved))
      .mockResolvedValueOnce(response({ items: [approved], total: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <RecommendedActions
        opportunityId="opportunity-1"
        initialActions={[action()]}
      />,
    );

    expect(
      screen.getByText("Customer-facing — review carefully"),
    ).toBeVisible();
    expect(
      screen.getByText(/Draft only — no recipient is treated as confirmed/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /^send|sync|schedule$/i }),
    ).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Approve action" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/actions/action-1/approve",
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      expectedVersion: 1,
    });
    expect(
      await screen.findByText(/Nothing was sent or updated/i),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Approved (1)" }));
    expect(screen.getByText("Approved — not sent or updated")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Mark complete manually" }),
    ).toBeNull();
  });

  it("edits safe fields by creating a new revision request with the typed payload intact", async () => {
    const edited = action({
      status: "edited",
      currentVersion: 2,
      title: "Review the updated follow-up",
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(edited))
      .mockResolvedValueOnce(response({ items: [edited], total: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <RecommendedActions
        opportunityId="opportunity-1"
        initialActions={[action()]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Edit suggestion" }));
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Review the updated follow-up" },
    });
    fireEvent.change(screen.getByLabelText("Email subject"), {
      target: { value: "Updated security review next steps" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save revision" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body)) as {
      expectedVersion: number;
      title: string;
      proposedPayload: {
        kind: string;
        subject: string;
        recipientConfirmed: boolean;
      };
    };
    expect(body.expectedVersion).toBe(1);
    expect(body.title).toBe("Review the updated follow-up");
    expect(body.proposedPayload).toMatchObject({
      kind: "follow_up_email",
      subject: "Updated security review next steps",
      recipientConfirmed: false,
    });
    expect(
      await screen.findByText("Your changes were saved for review."),
    ).toBeVisible();
  });

  it("uses a read-only server preview and a separate explicit simulation confirmation", async () => {
    const approved = action({
      status: "approved",
      approvedVersion: 1,
      approvedAt: "2026-08-15T03:00:00Z",
      proposedPayload: {
        kind: "follow_up_email",
        draftArtifactId: "artifact-1",
        recipientContactId: "contact-1",
        recipientEmail: "jordan@example.com",
        recipientConfirmed: true,
        subject: "Security review next steps",
        body: "Hello Jordan,\n\nThank you for the discussion.",
      },
    });
    const queued = {
      id: "execution-1",
      actionProposalId: approved.id,
      actionVersion: 1,
      connectionId: "connection-1",
      connectorKey: "mock_email",
      connectorDisplayName: "Mock Email",
      capability: "send_email",
      riskClass: "external_customer_facing",
      executionStatus: "queued",
      executionMode: "simulation",
      simulationOnly: true,
      confirmedByUserId: "user-1",
      confirmedAt: "2026-08-15T04:00:00Z",
      startedAt: null,
      completedAt: null,
      failedAt: null,
      safeFailureCode: null,
      externalResultId: null,
      attemptCount: 0,
      retryable: false,
      safeMessage: "Simulation queued. No external action has occurred.",
      createdAt: "2026-08-15T04:00:00Z",
      updatedAt: "2026-08-15T04:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response({
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
        }),
      )
      .mockResolvedValueOnce(
        response({
          id: "preview-1",
          actionProposalId: approved.id,
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
          previewFingerprint: "f".repeat(64),
          content: {
            kind: "email",
            recipient: "jordan@example.com",
            subject: "Security review next steps",
            body: "Hello Jordan,\n\nThank you for the discussion.",
            action: "send_email",
          },
          expiresAt: "2026-08-15T04:10:00Z",
          createdAt: "2026-08-15T04:00:00Z",
        }),
      )
      .mockResolvedValueOnce(response({ items: [], total: 0 }))
      .mockResolvedValueOnce(response(queued))
      .mockResolvedValueOnce(
        response({
          ...queued,
          executionStatus: "simulated_success",
          externalResultId: "mock_email_result_1",
          attemptCount: 1,
          safeMessage: "Simulation completed. No external action occurred.",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <RecommendedActions
        opportunityId="opportunity-1"
        initialActions={[approved]}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Approved (1)" }));
    fireEvent.click(screen.getByRole("button", { name: "Preview simulation" }));
    expect(
      await screen.findByText("Simulation — no external action will occur"),
    ).toBeVisible();
    expect(screen.getByText("jordan@example.com")).toBeVisible();
    expect(screen.queryByRole("textbox")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Send email" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body))).toEqual({
      previewId: "preview-1",
      connectionId: "connection-1",
      confirmed: true,
    });
    expect(await screen.findByText("Simulation in progress")).toBeVisible();

    fireEvent.click(
      screen.getByRole("button", { name: "Refresh simulation status" }),
    );
    expect(await screen.findByText("Simulation complete")).toBeVisible();
    expect(screen.getByText(/mock_email_result_1/)).toBeVisible();
  });
});
