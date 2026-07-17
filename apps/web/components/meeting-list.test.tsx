import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeetingList } from "@/components/meeting-list";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const meetingPage = {
  items: [
    {
      id: "meeting-1",
      organisationId: "organisation-1",
      title: "Acme discovery",
      description: "Discovery call",
      meetingDate: "2026-08-01T00:00:00Z",
      meetingType: "remote",
      status: "scheduled",
      companyId: "company-1",
      ownerUserId: "user-1",
      createdBy: "user-1",
      updatedBy: "user-1",
      createdAt: "2026-07-17T00:00:00Z",
      updatedAt: "2026-07-17T00:00:00Z",
    },
  ],
  page: 1,
  pageSize: 20,
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

describe("MeetingList", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders loading, desktop and mobile records, and detail navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          jsonResponse(
            String(input).includes("/meetings") ? meetingPage : companyPage,
          ),
        ),
      ),
    );

    render(<MeetingList />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading meetings");
    expect(await screen.findAllByText("Acme discovery")).toHaveLength(2);
    expect(screen.getAllByText("Acme Australia")).toHaveLength(2);
    expect(
      screen.getByRole("link", { name: "Create meeting" }),
    ).toHaveAttribute("href", "/meetings/new");
    expect(
      screen.getAllByRole("link", { name: "Acme discovery" })[0],
    ).toHaveAttribute("href", "/meetings/meeting-1");
  });

  it("applies search and filters and renders a recoverable empty state", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        jsonResponse(
          String(input).includes("/meetings")
            ? { ...meetingPage, items: [], total: 0, pages: 0 }
            : { ...companyPage, items: [], total: 0, pages: 0 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingList />);
    expect(
      await screen.findByRole("heading", { name: "No meetings found" }),
    ).toBeVisible();

    fireEvent.change(screen.getByLabelText("Search meetings"), {
      target: { value: "Acme discovery" },
    });
    fireEvent.change(screen.getByLabelText("Filter by status"), {
      target: { value: "scheduled" },
    });
    fireEvent.change(screen.getByLabelText("Filter by meeting type"), {
      target: { value: "remote" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => {
          const url = String(call[0]);
          return (
            url.includes("search=Acme+discovery") &&
            url.includes("status=scheduled") &&
            url.includes("meetingType=remote")
          );
        }),
      ).toBe(true),
    );
  });

  it("shows a safe error with retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            code: "persistence_unavailable",
            message: "Persistence is unavailable.",
            requestId: "request-1",
          },
          503,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(companyPage))
      .mockResolvedValueOnce(
        jsonResponse({ ...meetingPage, items: [], total: 0, pages: 0 }),
      )
      .mockResolvedValueOnce(jsonResponse(companyPage));
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingList />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Persistence is unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No meetings found" }),
    ).toBeVisible();
  });
});
