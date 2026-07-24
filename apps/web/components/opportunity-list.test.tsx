import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OpportunityList } from "@/components/opportunity-list";

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const opportunity = {
  id: "opportunity-1",
  organisationId: "organisation-1",
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
  description: null,
  latestMeetingId: "meeting-1",
  latestMeetingDate: "2026-08-01T00:00:00Z",
  latestMeetingMomentum: "positive",
  latestNextBestAction: "Confirm the procurement owner.",
  createdAt: "2026-07-20T00:00:00Z",
  updatedAt: "2026-07-24T00:00:00Z",
};

describe("OpportunityList", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders commercial context and latest-meeting previews", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          items: [opportunity],
          page: 1,
          pageSize: 20,
          total: 1,
          pages: 1,
        }),
      ),
    );
    render(<OpportunityList />);

    expect(await screen.findByText("Platform expansion")).toBeVisible();
    expect(screen.getByText("Acme Australia")).toBeVisible();
    expect(screen.getByText("Positive")).toBeVisible();
    expect(screen.getByText("Confirm the procurement owner.")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Platform expansion" }),
    ).toHaveAttribute("href", "/opportunities/opportunity-1");
    expect(
      screen.queryByText(/probability|forecast|health score/i),
    ).not.toBeInTheDocument();
  });

  it("supports deterministic filters and a clear empty state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        response({ items: [], page: 1, pageSize: 20, total: 0, pages: 0 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityList />);

    expect(
      await screen.findByRole("heading", { name: "No opportunities yet" }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Stage"), {
      target: { value: "evaluation" },
    });
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "on_hold" },
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const latestUrl = String(fetchMock.mock.calls.at(-1)?.[0]);
    expect(latestUrl).toContain("sortBy=updated_at");
    expect(latestUrl).toContain("sortOrder=desc");
    expect(latestUrl).toContain("stage=evaluation");
    expect(latestUrl).toContain("status=on_hold");
  });

  it("shows a recoverable safe error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response(
          {
            code: "persistence_unavailable",
            message: "Opportunities are temporarily unavailable.",
            requestId: "request-1",
          },
          503,
        ),
      )
      .mockResolvedValueOnce(
        response({ items: [], page: 1, pageSize: 20, total: 0, pages: 0 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityList />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Opportunities are temporarily unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "No opportunities yet" }),
    ).toBeVisible();
  });
});
