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

    fireEvent.click(
      screen.getByRole("button", { name: "Approve — do not execute" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/actions/action-1/approve",
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      expectedVersion: 1,
    });
    expect(
      await screen.findByText(/Nothing was sent, synced or executed/i),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Approved (1)" }));
    expect(screen.getByText("Approved — not yet executed")).toBeVisible();
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

    fireEvent.click(screen.getByRole("button", { name: "Edit proposal" }));
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
      await screen.findByText("A new Action revision was saved for review."),
    ).toBeVisible();
  });
});
