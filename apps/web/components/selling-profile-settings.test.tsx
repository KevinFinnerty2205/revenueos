import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type {
  SellingProfileContent,
  SellingProfileManagement,
  SellingProfileRevision,
} from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SellingProfileSettings } from "@/components/selling-profile-settings";

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const content: SellingProfileContent = {
  companyDescription: "We help relationship-led sales teams preserve context.",
  offerings: [
    {
      name: "Sales Brain",
      description: "A reviewed relationship-intelligence workspace.",
      whoNormallyBuys: ["Founder-led sales teams"],
      problemsSolved: [],
      intendedOutcomes: [],
      differentiators: [],
      competitorsAlternatives: [],
      approvedProof: [],
      approvedClaims: [],
    },
  ],
};

function revision(
  state: SellingProfileRevision["state"] = "draft",
): SellingProfileRevision {
  return {
    id: `revision-${state}`,
    profileId: "profile-1",
    revisionNumber: state === "superseded" ? 1 : 2,
    state,
    lockVersion: 1,
    content,
    contentFingerprint: "a".repeat(64),
    createdByUserId: "user-1",
    approvedByUserId: state === "draft" ? null : "user-1",
    createdAt: "2026-09-04T00:00:00Z",
    updatedAt: "2026-09-04T00:00:00Z",
    approvedAt: state === "draft" ? null : "2026-09-04T00:00:00Z",
    supersededAt: state === "superseded" ? "2026-09-04T00:00:00Z" : null,
    retiredAt: state === "retired" ? "2026-09-04T00:00:00Z" : null,
  };
}

function profile(
  overrides: Partial<SellingProfileManagement> = {},
): SellingProfileManagement {
  return {
    status: "empty",
    canManage: true,
    draft: null,
    current: null,
    history: [],
    authority: "organisation_approved",
    authorityNote: "Organisation-approved context only.",
    ...overrides,
  };
}

describe("SellingProfileSettings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows loading, a safe recoverable error and then the empty form", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response(
          {
            code: "selling_profile_unavailable",
            message: "The profile could not be loaded.",
          },
          503,
        ),
      )
      .mockResolvedValueOnce(response(profile()));
    vi.stubGlobal("fetch", fetchMock);
    render(<SellingProfileSettings />);

    expect(screen.getByRole("status")).toHaveTextContent(/Loading Company/i);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The profile could not be loaded.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("New draft")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Company & Selling Profile" }),
    ).toBeVisible();
  });

  it("creates a minimal draft and keeps approval separate", async () => {
    const draft = revision();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(profile()))
      .mockResolvedValueOnce(
        response(profile({ status: "draft", draft, history: [draft] }), 201),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<SellingProfileSettings />);

    expect(
      await screen.findByRole("heading", { name: "Company & Selling Profile" }),
    ).toBeVisible();
    expect(
      screen.getByText(/not customer Evidence, prospect research, CRM truth/i),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText(/^Company description/i), {
      target: { value: content.companyDescription },
    });
    fireEvent.change(screen.getByLabelText("Offering name"), {
      target: { value: "Sales Brain" },
    });
    fireEvent.change(screen.getByLabelText("Concise description"), {
      target: { value: "A reviewed relationship-intelligence workspace." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await screen.findByText(/Draft revision 2 saved/i);
    expect(
      screen.getByRole("button", { name: "Approve as current" }),
    ).toBeVisible();
    const submitted = JSON.parse(
      String((fetchMock.mock.calls[1]?.[1] as RequestInit).body),
    );
    expect(submitted.content.offerings).toHaveLength(1);
    expect(submitted.content.companyDescription).toBe(
      content.companyDescription,
    );
  });

  it("edits optional approved fields and approves the current draft", async () => {
    const draft = revision();
    const approved = {
      ...draft,
      state: "approved" as const,
      approvedByUserId: "user-1",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response(profile({ status: "draft", draft, history: [draft] })),
      )
      .mockResolvedValueOnce(
        response(
          profile({
            status: "current",
            current: approved,
            history: [approved],
          }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<SellingProfileSettings />);

    await screen.findByText("Draft revision 2");
    fireEvent.click(screen.getByText("Optional approved selling context"));
    expect(screen.getByLabelText(/Who normally buys/i)).toHaveValue(
      "Founder-led sales teams",
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve as current" }));

    expect(
      await screen.findByText(/is now the approved current context/i),
    ).toBeVisible();
    expect(screen.getByText("Approved current")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("retires the approved projection without deleting its history", async () => {
    const current = revision("approved");
    const retired = {
      ...current,
      state: "retired" as const,
      retiredAt: "2026-09-04T01:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response(profile({ status: "current", current, history: [current] })),
      )
      .mockResolvedValueOnce(
        response(profile({ status: "retired", history: [retired] })),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<SellingProfileSettings />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Retire current profile" }),
    );
    await screen.findByText(/Members no longer receive it/i);
    fireEvent.click(screen.getByText(/Revision history/));
    expect(screen.getAllByText(/retired/i).length).toBeGreaterThan(0);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
