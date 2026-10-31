import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { EntityPage, OpportunityListItem } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountOpportunityPanel } from "@/components/account-opportunity-panel";
import { apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
const mockedApiRequest = vi.mocked(apiRequest);

const opportunity: OpportunityListItem = {
  id: "opportunity-1",
  organisationId: "organisation-1",
  companyId: "company/one",
  companyName: "[DEMO] Northstar Facilities Group",
  name: "[DEMO] National portfolio expansion",
  stage: "evaluation",
  status: "open",
  estimatedValue: "125000.00",
  currency: "aud",
  expectedCloseDate: "2026-11-30",
  ownerUserId: "user-1",
  ownerName: "Alex Morgan",
  description: null,
  archivedAt: null,
  latestMeetingId: null,
  latestMeetingDate: null,
  latestMeetingMomentum: null,
  latestNextBestAction: null,
  createdAt: "2026-10-24T00:00:00Z",
  updatedAt: "2026-10-24T00:00:00Z",
};

function page(
  items: OpportunityListItem[],
  total = items.length,
): EntityPage<OpportunityListItem> {
  return {
    items,
    page: 1,
    pageSize: 20,
    total,
    pages: total ? Math.ceil(total / 20) : 0,
  };
}

afterEach(() => {
  mockedApiRequest.mockReset();
});

describe("AccountOpportunityPanel", () => {
  it("loads only open Opportunities for the exact Account and links the workspace", async () => {
    mockedApiRequest.mockResolvedValueOnce(page([opportunity]));

    render(<AccountOpportunityPanel companyId="company/one" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading open Opportunities",
    );
    expect(
      await screen.findByRole("link", {
        name: "[DEMO] National portfolio expansion",
      }),
    ).toHaveAttribute("href", "/opportunities/opportunity-1");
    expect(screen.getByText("Evaluation · Alex Morgan")).toBeVisible();
    expect(screen.getByText(/AUD.*125,000/)).toHaveTextContent(
      "Expected close 30 Nov 2026",
    );
    expect(
      screen.getByRole("link", { name: "Add Opportunity" }),
    ).toHaveAttribute("href", "/opportunities/new?companyId=company%2Fone");
    expect(mockedApiRequest).toHaveBeenCalledWith(
      "/api/v1/opportunities?companyId=company%2Fone&status=open&page=1&pageSize=20&sortBy=updated_at&sortOrder=desc",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows an honest empty state", async () => {
    mockedApiRequest.mockResolvedValueOnce(page([]));

    render(<AccountOpportunityPanel companyId="company-1" />);

    expect(
      await screen.findByText(
        "No open Opportunities are linked to this Account yet.",
      ),
    ).toBeVisible();
  });

  it("makes a truncated Account preview explicit", async () => {
    mockedApiRequest.mockResolvedValueOnce(page([opportunity], 25));

    render(<AccountOpportunityPanel companyId="company-1" />);

    expect(await screen.findByText(/Showing 1 of 25/)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "View the full Pipeline" }),
    ).toHaveAttribute("href", "/opportunities");
  });

  it("offers a bounded retry after a load failure", async () => {
    mockedApiRequest
      .mockRejectedValueOnce(
        new Error("Opportunities are temporarily unavailable."),
      )
      .mockResolvedValueOnce(page([opportunity]));

    render(<AccountOpportunityPanel companyId="company-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Opportunities are temporarily unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(mockedApiRequest).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByRole("link", {
        name: "[DEMO] National portfolio expansion",
      }),
    ).toBeVisible();
  });
});
