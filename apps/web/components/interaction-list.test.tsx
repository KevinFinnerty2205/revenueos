import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InteractionList } from "@/components/interaction-list";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const interactionPage = {
  items: [
    {
      id: "interaction-1",
      organisationId: "organisation-1",
      companyId: "company-1",
      opportunityId: null,
      meetingId: "meeting-1",
      interactionType: "online_meeting",
      lifecycleStatus: "planned",
      title: "Acme discovery",
      scheduledStartAt: "2026-08-01T00:00:00Z",
      scheduledEndAt: null,
      actualStartAt: null,
      actualEndAt: null,
      timezone: "Australia/Sydney",
      creationOrigin: "meeting_compatibility",
      createdByUserId: "user-1",
      briefState: "completed",
      briefGeneratedAt: "2026-07-26T00:00:00Z",
      createdAt: "2026-07-26T00:00:00Z",
      updatedAt: "2026-07-26T00:00:00Z",
    },
  ],
  page: 1,
  pageSize: 100,
  total: 1,
  pages: 1,
};

const companyPage = {
  items: [{ id: "company-1", name: "Acme Australia" }],
  page: 1,
  pageSize: 100,
  total: 1,
  pages: 1,
};

describe("InteractionList", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders loading, provenance-neutral records and compatibility navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          jsonResponse(
            String(input).includes("/interactions")
              ? interactionPage
              : companyPage,
          ),
        ),
      ),
    );

    render(<InteractionList />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading interactions",
    );
    expect(
      await screen.findByRole("heading", { name: "Acme discovery" }),
    ).toBeVisible();
    expect(screen.getByText("Acme Australia")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open Meeting Intelligence" }),
    ).toHaveAttribute("href", "/meetings/meeting-1");
    expect(screen.getByText("Brief ready")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open brief" })).toHaveAttribute(
      "href",
      "/interactions/interaction-1#preparation",
    );
    expect(
      screen.queryByText(/prompt|provider|worker/i),
    ).not.toBeInTheDocument();
  });

  it("applies accessible filters and presents a useful empty state", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        jsonResponse(
          String(input).includes("/interactions")
            ? { ...interactionPage, items: [], total: 0, pages: 0 }
            : companyPage,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", { name: "No interactions found" }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Search interactions"), {
      target: { value: "Acme discovery" },
    });
    fireEvent.change(screen.getByLabelText("Filter by type"), {
      target: { value: "online_meeting" },
    });
    fireEvent.change(screen.getByLabelText("Filter by status"), {
      target: { value: "planned" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) => {
          const url = String(input);
          return (
            url.includes("search=Acme+discovery") &&
            url.includes("interactionType=online_meeting") &&
            url.includes("status=planned")
          );
        }),
      ).toBe(true),
    );
  });

  it("shows a safe error and supports retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            code: "persistence_unavailable",
            message: "Interactions are temporarily unavailable.",
            requestId: "request-1",
          },
          503,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(companyPage))
      .mockResolvedValueOnce(
        jsonResponse({ ...interactionPage, items: [], total: 0, pages: 0 }),
      )
      .mockResolvedValueOnce(jsonResponse(companyPage));
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionList />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Interactions are temporarily unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No interactions found" }),
    ).toBeVisible();
  });
});
