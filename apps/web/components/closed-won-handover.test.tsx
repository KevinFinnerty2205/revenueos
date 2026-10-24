import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type {
  HandoverContent,
  HandoverRevision,
  HandoverWorkspace,
} from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ClosedWonHandover } from "@/components/closed-won-handover";
import { apiRequest } from "@/lib/api";
import { notifyOpportunityChanged } from "@/lib/opportunity-events";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
const mockedApiRequest = vi.mocked(apiRequest);

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
} {
  let resolve: ((value: T) => void) | undefined;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return {
    promise,
    resolve(value: T) {
      if (!resolve) throw new Error("Deferred promise was not initialised.");
      resolve(value);
    },
  };
}

const emptyContent: HandoverContent = {
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

function revision(overrides: Partial<HandoverRevision> = {}): HandoverRevision {
  return {
    id: "revision-1",
    handoverId: "handover-1",
    opportunityId: "opportunity-1",
    revision: 1,
    status: "draft",
    contentSchemaVersion: 1,
    content: {
      ...emptyContent,
      executiveSummary: [
        {
          id: "item-1",
          text: "Internal transition handover for Harbour rollout.",
          authorityType: "system_derived",
          sourceIds: ["source-1"],
          confirmedByUserId: null,
          confirmedAt: null,
          owner: null,
          dueDate: null,
          actionStatus: null,
          riskKind: null,
        },
      ],
    },
    sources: [
      {
        id: "source-1",
        sourceType: "opportunity",
        sourceId: "opportunity-1",
        sourceVersionId: null,
        sourceVersion: null,
        authorityType: "commercial_record",
        label: "Canonical Opportunity record",
        sourceFingerprint: "a".repeat(64),
        pinnedAt: "2026-09-08T00:00:00Z",
      },
    ],
    lockVersion: 1,
    approvalBlockers: [],
    createdByUserId: "user-1",
    submittedAt: null,
    approvedByUserId: null,
    approvedAt: null,
    supersededAt: null,
    retiredAt: null,
    retirementReason: null,
    createdAt: "2026-09-08T00:00:00Z",
    updatedAt: "2026-09-08T00:00:00Z",
    ...overrides,
  };
}

function workspace(
  overrides: Partial<HandoverWorkspace> = {},
): HandoverWorkspace {
  return {
    handoverId: "handover-1",
    opportunityId: "opportunity-1",
    opportunityStatus: "open",
    handoverLockVersion: 1,
    activeRevision: revision(),
    currentApprovedRevision: null,
    history: [],
    canManage: true,
    canApprove: true,
    entitlement: "create",
    creditsRequired: false,
    aiDrafting: "not_used",
    ...overrides,
  };
}

describe("ClosedWonHandover", () => {
  afterEach(() => mockedApiRequest.mockReset());

  it("contains a malformed handover response without crashing the Opportunity page", async () => {
    mockedApiRequest.mockResolvedValueOnce({ items: [] });

    render(<ClosedWonHandover opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", { name: "Closed-Won Handover" }),
    ).toBeVisible();
    expect(
      screen.getByText(/service returned an invalid response/i),
    ).toBeVisible();
  });

  it("prepares an explicitly non-AI draft from the Opportunity Workspace", async () => {
    mockedApiRequest
      .mockResolvedValueOnce(
        workspace({
          handoverId: null,
          handoverLockVersion: null,
          activeRevision: null,
        }),
      )
      .mockResolvedValueOnce(workspace());

    render(<ClosedWonHandover opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", {
        name: "Prepare a Closed-Won Handover",
      }),
    ).toBeVisible();
    expect(screen.getByText(/does not call an AI provider/i)).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Prepare handover draft" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Closed-Won Handover · revision 1",
      }),
    ).toBeVisible();
    expect(screen.getByText(/No Credits required/i)).toBeVisible();
    expect(mockedApiRequest).toHaveBeenLastCalledWith(
      "/api/v1/opportunities/opportunity-1/handover/prepare",
      { method: "POST" },
    );
  });

  it("requires explicit review confirmation before refreshing pinned sources", async () => {
    mockedApiRequest.mockResolvedValueOnce(workspace());

    render(<ClosedWonHandover opportunityId="opportunity-1" />);

    const refresh = await screen.findByRole("button", {
      name: "Refresh pinned sources",
    });
    expect(refresh).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", { name: /I reviewed the claims/i }),
    );
    expect(refresh).toBeEnabled();
  });

  it("marks manual edits as reviewed draft work and submits with optimistic locks", async () => {
    const initial = workspace();
    const savedRevision = revision({
      lockVersion: 2,
      content: {
        ...initial.activeRevision!.content,
        executiveSummary: [
          {
            ...initial.activeRevision!.content.executiveSummary[0]!,
            text: "Seller-reviewed transition summary.",
            authorityType: "seller_confirmed",
            confirmedByUserId: "user-1",
            confirmedAt: "2026-09-08T01:00:00Z",
          },
        ],
      },
    });
    const saved = workspace({
      handoverLockVersion: 2,
      activeRevision: savedRevision,
    });
    const submitted = workspace({
      handoverLockVersion: 3,
      activeRevision: revision({
        ...savedRevision,
        status: "in_review",
        lockVersion: 3,
        submittedAt: "2026-09-08T01:05:00Z",
      }),
    });
    mockedApiRequest
      .mockResolvedValueOnce(initial)
      .mockResolvedValueOnce(saved)
      .mockResolvedValueOnce(submitted);

    render(<ClosedWonHandover opportunityId="opportunity-1" />);
    fireEvent.change(await screen.findByLabelText("Executive summary item 1"), {
      target: { value: "Seller-reviewed transition summary." },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save reviewed draft" }),
    );
    expect(
      await screen.findByText(/Changed claims are now recorded/i),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("checkbox", { name: /I reviewed the claims/i }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));

    await waitFor(() =>
      expect(mockedApiRequest).toHaveBeenLastCalledWith(
        "/api/v1/opportunities/opportunity-1/handover/revisions/revision-1/submit",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            expectedHandoverVersion: 2,
            expectedRevisionVersion: 2,
            confirmed: true,
          }),
        }),
      ),
    );
  });

  it("blocks approval for inference and while the canonical Opportunity remains open", async () => {
    const inferredItem = {
      ...revision().content.executiveSummary[0]!,
      id: "inference-1",
      text: "Possible unverified implementation promise.",
      authorityType: "inference" as const,
      sourceIds: [],
    };
    mockedApiRequest.mockResolvedValueOnce(
      workspace({
        activeRevision: revision({
          status: "in_review",
          submittedAt: "2026-09-08T01:00:00Z",
          content: { ...emptyContent, commitments: [inferredItem] },
          approvalBlockers: [
            "commitments: confirm or remove the inference before approval.",
          ],
        }),
      }),
    );

    render(<ClosedWonHandover opportunityId="opportunity-1" />);

    expect(
      await screen.findByText("Review required before approval"),
    ).toBeVisible();
    expect(screen.getByText(/confirm or remove the inference/i)).toBeVisible();
    expect(
      screen.getByText(/canonical Opportunity status is Closed Won/i),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("checkbox", { name: /I reviewed the claims/i }),
    );
    expect(
      screen.getByRole("button", { name: "Approve immutable handover" }),
    ).toBeDisabled();
  });

  it("refreshes the approval boundary when the sibling pipeline closes Won", async () => {
    const review = revision({
      status: "in_review",
      submittedAt: "2026-09-08T01:00:00Z",
      approvalBlockers: [],
    });
    mockedApiRequest
      .mockResolvedValueOnce(workspace({ activeRevision: review }))
      .mockResolvedValueOnce(
        workspace({ opportunityStatus: "won", activeRevision: review }),
      );

    render(<ClosedWonHandover opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("button", { name: "Approve immutable handover" }),
    ).toBeDisabled();
    act(() => notifyOpportunityChanged("opportunity-1", "won"));
    await waitFor(() => expect(mockedApiRequest).toHaveBeenCalledTimes(2));
    fireEvent.click(
      screen.getByRole("checkbox", { name: /I reviewed the claims/i }),
    );
    expect(
      screen.getByRole("button", { name: "Approve immutable handover" }),
    ).toBeEnabled();
  });

  it("preserves unsaved handover edits when the Opportunity status refreshes", async () => {
    const review = revision({
      status: "in_review",
      submittedAt: "2026-09-08T01:00:00Z",
      approvalBlockers: [],
    });
    mockedApiRequest
      .mockResolvedValueOnce(workspace({ activeRevision: review }))
      .mockResolvedValueOnce(
        workspace({ opportunityStatus: "won", activeRevision: review }),
      );

    render(<ClosedWonHandover opportunityId="opportunity-1" />);

    const summary = await screen.findByLabelText("Executive summary item 1");
    fireEvent.change(summary, {
      target: { value: "Unsaved seller clarification." },
    });
    act(() => notifyOpportunityChanged("opportunity-1", "won"));

    expect(
      await screen.findByText(/unsaved handover edits were preserved/i),
    ).toBeVisible();
    expect(screen.getByLabelText("Executive summary item 1")).toHaveValue(
      "Unsaved seller clarification.",
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: /I reviewed the claims/i }),
    );
    expect(
      screen.getByRole("button", { name: "Approve immutable handover" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Save reviewed draft" }),
    ).toBeEnabled();
  });

  it("ignores an aborted status response without losing the latest dirty handover snapshot", async () => {
    const review = revision({
      status: "in_review",
      submittedAt: "2026-09-08T01:00:00Z",
      approvalBlockers: [],
    });
    const closing = deferred<HandoverWorkspace>();
    const reopening = deferred<HandoverWorkspace>();
    mockedApiRequest
      .mockResolvedValueOnce(workspace({ activeRevision: review }))
      .mockImplementationOnce(() => closing.promise)
      .mockImplementationOnce(() => reopening.promise);

    render(<ClosedWonHandover opportunityId="opportunity-1" />);

    fireEvent.change(await screen.findByLabelText("Executive summary item 1"), {
      target: { value: "Keep this unsaved handover clarification." },
    });
    act(() => notifyOpportunityChanged("opportunity-1", "won"));
    await waitFor(() => expect(mockedApiRequest).toHaveBeenCalledTimes(2));

    act(() => notifyOpportunityChanged("opportunity-1", "open"));
    await waitFor(() => expect(mockedApiRequest).toHaveBeenCalledTimes(3));

    await act(async () => {
      closing.resolve(
        workspace({ opportunityStatus: "won", activeRevision: review }),
      );
      await Promise.resolve();
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      /Loading Closed-Won Handover/i,
    );

    await act(async () => {
      reopening.resolve(workspace({ activeRevision: review }));
      await Promise.resolve();
    });

    expect(
      await screen.findByText(/unsaved handover edits were preserved/i),
    ).toBeVisible();
    expect(screen.getByLabelText("Executive summary item 1")).toHaveValue(
      "Keep this unsaved handover clarification.",
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: /I reviewed the claims/i }),
    );
    expect(
      screen.getByRole("button", { name: "Approve immutable handover" }),
    ).toBeDisabled();
  });

  it("renders an approved immutable document and opens retired history", async () => {
    const approved = revision({
      status: "approved",
      approvedAt: "2026-09-08T02:00:00Z",
      approvedByUserId: "admin-1",
    });
    const retired = revision({
      id: "revision-old",
      revision: 1,
      status: "retired",
      retiredAt: "2026-09-07T02:00:00Z",
      retirementReason: "opportunity_reopened",
    });
    mockedApiRequest
      .mockResolvedValueOnce(
        workspace({
          opportunityStatus: "won",
          activeRevision: { ...approved, revision: 2 },
          currentApprovedRevision: { ...approved, revision: 2 },
          history: [{ ...approved, revision: 2 }, retired],
        }),
      )
      .mockResolvedValueOnce(retired);

    render(<ClosedWonHandover opportunityId="opportunity-1" />);
    expect(
      await screen.findByText(/Internal transition handover/i),
    ).toBeVisible();
    expect(
      screen.queryByLabelText("Executive summary item 1"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Revision history/));
    const history = screen.getByText(/Revision history/).closest("details");
    expect(history).not.toBeNull();
    fireEvent.click(
      within(history!).getByRole("button", { name: "View revision 1" }),
    );
    expect(
      await screen.findByText(/Closed-Won Handover · revision 1/i),
    ).toBeVisible();
    expect(screen.getAllByText("retired").length).toBeGreaterThan(0);
  });
});
