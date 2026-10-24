import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { DealRoomMutation, DealRoomWorkspace } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DealRoomEditor } from "@/components/deal-room-editor";
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

const emptyDraft = {
  overview: null,
  commercialSummary: null,
  businessCaseVersionId: null,
  stakeholders: [],
  milestones: [],
  resources: [],
  nextMeetingAt: null,
};

function workspace(
  overrides: Partial<DealRoomWorkspace> = {},
): DealRoomWorkspace {
  return {
    opportunityStatus: "open",
    canEdit: true,
    canManageAccess: true,
    room: {
      id: "room-1",
      opportunityId: "opportunity-1",
      status: "draft",
      effectiveAccess: "unavailable",
      draftVersion: 1,
      lockVersion: 1,
      draft: emptyDraft,
      publishedRevisionId: null,
      publishedRevision: null,
      lastPublishedAt: null,
      link: { active: false, expiresAt: null, createdAt: null },
      revisions: [],
      createdAt: "2026-09-07T00:00:00Z",
      updatedAt: "2026-09-07T00:00:00Z",
    },
    businessCases: [
      {
        caseId: "case-1",
        versionId: "case-version-1",
        title: "Approved rollout case",
        version: 2,
        approvedAt: "2026-09-07T00:00:00Z",
      },
    ],
    presentations: [
      {
        presentationId: "presentation-1",
        versionId: "presentation-version-1",
        title: "Approved solution overview",
        version: 3,
        approvedAt: "2026-09-07T00:00:00Z",
      },
    ],
    entitlement: "create",
    creditsRequired: false,
    ...overrides,
  };
}

describe("DealRoomEditor", () => {
  afterEach(() => {
    mockedApiRequest.mockReset();
    vi.unstubAllGlobals();
  });

  it("creates an explicitly private draft from the Opportunity Workspace", async () => {
    const missing = workspace({ room: null });
    const created = workspace();
    mockedApiRequest
      .mockResolvedValueOnce(missing)
      .mockResolvedValueOnce({ workspace: created, shareToken: null });

    render(<DealRoomEditor opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", { name: "Create a simple Deal Room" }),
    ).toBeVisible();
    expect(screen.getByText(/Nothing is public yet/i)).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Create Deal Room draft" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Opportunity Deal Room" }),
    ).toBeVisible();
    expect(screen.getByText(/no Oryntela Credits/i)).toBeVisible();
    expect(mockedApiRequest).toHaveBeenLastCalledWith(
      "/api/v1/opportunities/opportunity-1/deal-room",
      { method: "POST" },
    );
  });

  it("refreshes after an Opportunity lifecycle change and blocks creation once closed", async () => {
    mockedApiRequest
      .mockResolvedValueOnce(workspace({ room: null }))
      .mockResolvedValueOnce(
        workspace({ room: null, opportunityStatus: "won", canEdit: false }),
      );

    render(<DealRoomEditor opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("button", { name: "Create Deal Room draft" }),
    ).toBeEnabled();
    act(() => notifyOpportunityChanged("opportunity-1", "won"));

    expect(
      await screen.findByText(
        /Editing is unavailable while this Opportunity is won/i,
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Create Deal Room draft" }),
    ).toBeDisabled();
    expect(mockedApiRequest).toHaveBeenCalledTimes(2);
  });

  it("preserves unsaved Deal Room edits when only an open stage changes", async () => {
    mockedApiRequest.mockResolvedValueOnce(workspace());

    render(<DealRoomEditor opportunityId="opportunity-1" />);

    const overview = await screen.findByLabelText(/Customer-facing overview/i);
    fireEvent.change(overview, {
      target: { value: "Unsaved reviewed context" },
    });
    act(() => notifyOpportunityChanged("opportunity-1", "open"));

    expect(overview).toHaveValue("Unsaved reviewed context");
    expect(mockedApiRequest).toHaveBeenCalledTimes(1);
  });

  it("preserves unsaved Deal Room edits across close and reopen status refreshes", async () => {
    mockedApiRequest
      .mockResolvedValueOnce(workspace())
      .mockResolvedValueOnce(
        workspace({ opportunityStatus: "won", canEdit: false }),
      )
      .mockResolvedValueOnce(workspace());

    render(<DealRoomEditor opportunityId="opportunity-1" />);

    fireEvent.change(
      await screen.findByLabelText(/Customer-facing overview/i),
      { target: { value: "Unsaved reviewed context" } },
    );
    fireEvent.change(screen.getByLabelText(/Link expiry/i), {
      target: { value: "2026-10-31T09:30" },
    });

    act(() => notifyOpportunityChanged("opportunity-1", "won"));

    expect(
      await screen.findByText(/unsaved Deal Room edits were preserved/i),
    ).toHaveTextContent(/read-only; reopen it before saving/i);
    expect(screen.getByLabelText(/Customer-facing overview/i)).toHaveValue(
      "Unsaved reviewed context",
    );
    expect(screen.getByLabelText(/Link expiry/i)).toHaveValue(
      "2026-10-31T09:30",
    );
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();

    act(() => notifyOpportunityChanged("opportunity-1", "open"));

    expect(
      await screen.findByText(/save them before publishing/i),
    ).toBeVisible();
    expect(screen.getByLabelText(/Customer-facing overview/i)).toHaveValue(
      "Unsaved reviewed context",
    );
    expect(screen.getByLabelText(/Link expiry/i)).toHaveValue(
      "2026-10-31T09:30",
    );
    expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled();
    expect(mockedApiRequest).toHaveBeenCalledTimes(3);
  });

  it("ignores an aborted status response without losing the latest dirty Deal Room snapshot", async () => {
    const closing = deferred<DealRoomWorkspace>();
    const reopening = deferred<DealRoomWorkspace>();
    mockedApiRequest
      .mockResolvedValueOnce(workspace())
      .mockImplementationOnce(() => closing.promise)
      .mockImplementationOnce(() => reopening.promise);

    render(<DealRoomEditor opportunityId="opportunity-1" />);

    fireEvent.change(
      await screen.findByLabelText(/Customer-facing overview/i),
      { target: { value: "Keep this unsaved Deal Room context" } },
    );
    act(() => notifyOpportunityChanged("opportunity-1", "won"));
    await waitFor(() => expect(mockedApiRequest).toHaveBeenCalledTimes(2));

    act(() => notifyOpportunityChanged("opportunity-1", "open"));
    await waitFor(() => expect(mockedApiRequest).toHaveBeenCalledTimes(3));

    await act(async () => {
      closing.resolve(workspace({ opportunityStatus: "won", canEdit: false }));
      await Promise.resolve();
    });
    expect(screen.getByRole("status")).toHaveTextContent(/Loading Deal Room/i);

    await act(async () => {
      reopening.resolve(workspace());
      await Promise.resolve();
    });

    expect(
      await screen.findByText(/save them before publishing/i),
    ).toBeVisible();
    expect(screen.getByLabelText(/Customer-facing overview/i)).toHaveValue(
      "Keep this unsaved Deal Room context",
    );
    expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled();
  });

  it("keeps a closed Opportunity Deal Room inspectable without invalid edit actions", async () => {
    const initial = workspace();
    mockedApiRequest.mockResolvedValueOnce(
      workspace({
        opportunityStatus: "won",
        canEdit: false,
        room: {
          ...initial.room!,
          status: "published",
          publishedRevisionId: "revision-1",
          publishedRevision: 1,
        },
      }),
    );

    render(<DealRoomEditor opportunityId="opportunity-1" />);

    expect(await screen.findByText(/Deal Room is read-only/i)).toBeVisible();
    expect(screen.getByLabelText(/Customer-facing overview/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Review and republish" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Rotate link" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Pause access" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Revoke" })).toBeEnabled();
  });

  it("keeps edits in draft until reviewed publication and returns a fragment-only link", async () => {
    const initial = workspace();
    const saved = workspace({
      room: {
        ...initial.room!,
        draftVersion: 2,
        lockVersion: 2,
        draft: { ...emptyDraft, overview: "Agreed rollout objective" },
      },
    });
    const published = workspace({
      room: {
        ...saved.room!,
        status: "published",
        effectiveAccess: "available",
        lockVersion: 3,
        publishedRevisionId: "revision-1",
        publishedRevision: 1,
        lastPublishedAt: "2026-09-07T01:00:00Z",
        link: {
          active: true,
          expiresAt: null,
          createdAt: "2026-09-07T01:00:00Z",
        },
        revisions: [
          {
            id: "revision-1",
            revision: 1,
            publishedAt: "2026-09-07T01:00:00Z",
            publishedByUserId: "user-1",
            contentFingerprint: "a".repeat(64),
          },
        ],
      },
    });
    mockedApiRequest
      .mockResolvedValueOnce(initial)
      .mockResolvedValueOnce({ workspace: saved, shareToken: null })
      .mockResolvedValueOnce({
        workspace: published,
        shareToken: "secure_token_with_enough_entropy_1234567890",
      } satisfies DealRoomMutation);

    render(<DealRoomEditor opportunityId="opportunity-1" />);
    fireEvent.change(
      await screen.findByLabelText(/Customer-facing overview/i),
      {
        target: { value: "Agreed rollout objective" },
      },
    );
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /I have reviewed every field and selected resource/i,
      }),
    );
    expect(
      screen.getByRole("button", { name: "Review and publish" }),
    ).toBeDisabled();
    expect(screen.getByText(/Save this draft before reviewing/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(
      await screen.findByText(/Draft saved\. Nothing is public/i),
    ).toBeVisible();

    const publish = screen.getByRole("button", { name: "Review and publish" });
    expect(publish).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /I have reviewed every field and selected resource/i,
      }),
    );
    expect(publish).toBeEnabled();
    fireEvent.click(publish);

    const issued = await screen.findByLabelText("Secure buyer link");
    expect((issued as HTMLInputElement).value).toMatch(
      /\/deal-room#access=secure_token_with_enough_entropy_1234567890$/u,
    );
    expect(String((issued as HTMLInputElement).value)).not.toContain("?");
    await waitFor(() =>
      expect(mockedApiRequest).toHaveBeenLastCalledWith(
        "/api/v1/opportunities/opportunity-1/deal-room/publish",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });
});
