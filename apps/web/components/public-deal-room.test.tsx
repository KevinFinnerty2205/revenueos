import { render, screen } from "@testing-library/react";
import type { PublicDealRoomResolveResponse } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PublicDealRoom } from "@/components/public-deal-room";
import { apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiBlob: vi.fn(), apiRequest: vi.fn() }));
const mockedApiRequest = vi.mocked(apiRequest);

const projection: PublicDealRoomResolveResponse = {
  room: {
    schemaVersion: 1,
    revision: 2,
    publishedAt: "2026-09-07T01:00:00Z",
    sellerCompanyName: "Example Revenue Team",
    customerCompanyName: "Synthetic Customer",
    opportunityName: "Secure rollout",
    overview: "<script>window.intruded=true</script> Agreed objective",
    businessCase: {
      title: "Approved rollout case",
      version: 1,
      currency: "AUD",
      scenarios: [
        {
          name: "Base",
          outputs: [{ label: "First-year ROI", value: "42.0", unit: "%" }],
        },
      ],
    },
    commercialSummary: "Approved scope and 12-month term.",
    stakeholders: [
      {
        id: "stakeholder-1",
        name: "Jordan <img src=x onerror=alert(1)>",
        role: "Operations Director",
        company: "Synthetic Customer",
        party: "customer",
      },
    ],
    milestones: [
      {
        id: "milestone-1",
        title: "Complete security review",
        ownerParty: "joint",
        targetDate: "2026-09-18",
        status: "in_progress",
        note: "Review the approved questionnaire.",
      },
    ],
    resources: [
      {
        id: "resource-1",
        kind: "external_link",
        title: "Implementation guide",
        url: "https://example.com/implementation",
        downloadAvailable: false,
      },
    ],
    nextMeetingAt: "2026-09-12T03:00:00Z",
  },
  expiresAt: null,
};

describe("PublicDealRoom", () => {
  afterEach(() => {
    mockedApiRequest.mockReset();
    window.history.replaceState(null, "", "/");
  });

  it("renders the allow-listed buyer experience as text without app navigation or executable HTML", async () => {
    window.history.replaceState(
      null,
      "",
      "/deal-room#access=secure_token_with_enough_entropy_1234567890",
    );
    mockedApiRequest.mockResolvedValueOnce(projection);

    const { container } = render(<PublicDealRoom />);

    expect(
      await screen.findByRole("heading", { name: "Secure rollout" }),
    ).toBeVisible();
    expect(screen.getByText(/window\.intruded=true/u)).toBeVisible();
    expect(screen.getByText(/Jordan <img src=x/u)).toBeVisible();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(
      screen.queryByText(/MEDDIC|forecast probability|manager coaching/iu),
    ).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
    expect(screen.getByRole("link", { name: /Open resource/ })).toHaveAttribute(
      "referrerpolicy",
      "no-referrer",
    );
    expect(mockedApiRequest).toHaveBeenCalledWith(
      "/api/v1/deal-rooms/public/resolve",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          token: "secure_token_with_enough_entropy_1234567890",
        }),
      }),
    );
  });

  it("uses the same safe unavailable state without reflecting an invalid token", async () => {
    window.history.replaceState(
      null,
      "",
      "/deal-room#access=invalid-token-secret",
    );
    mockedApiRequest.mockRejectedValueOnce(new Error("Internal lookup failed"));

    render(<PublicDealRoom />);

    expect(
      await screen.findByRole("heading", {
        name: "This Deal Room is no longer available.",
      }),
    ).toBeVisible();
    expect(screen.queryByText("invalid-token-secret")).toBeNull();
    expect(screen.queryByText("Internal lookup failed")).toBeNull();
  });

  it("clears a previously rendered room when the fragment changes to a revoked link", async () => {
    window.history.replaceState(
      null,
      "",
      "/deal-room#access=secure_token_with_enough_entropy_1234567890",
    );
    mockedApiRequest
      .mockResolvedValueOnce(projection)
      .mockRejectedValueOnce(new Error("revoked"));
    render(<PublicDealRoom />);
    expect(
      await screen.findByRole("heading", { name: "Secure rollout" }),
    ).toBeVisible();

    window.history.replaceState(
      null,
      "",
      "/deal-room#access=revoked_token_with_enough_entropy_1234567890",
    );
    window.dispatchEvent(new HashChangeEvent("hashchange"));

    expect(
      await screen.findByRole("heading", {
        name: "This Deal Room is no longer available.",
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Secure rollout" }),
    ).toBeNull();
  });
});
