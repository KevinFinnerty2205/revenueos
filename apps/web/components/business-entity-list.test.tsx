import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BusinessEntityList } from "@/components/business-entity-list";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("BusinessEntityList", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders a loading state followed by company records and edit navigation", async () => {
    let resolveFetch: ((response: Response) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = resolve;
          }),
      ),
    );

    render(<BusinessEntityList entity="companies" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading companies");

    resolveFetch?.(
      jsonResponse({
        items: [
          {
            id: "company-1",
            organisationId: "organisation-1",
            name: "Acme Australia",
            website: null,
            industry: "Software",
            employeeCount: 125,
            status: "active",
            ownerUserId: "user-1",
            createdAt: "2026-07-17T00:00:00Z",
            updatedAt: "2026-07-17T00:00:00Z",
          },
        ],
        page: 1,
        pageSize: 20,
        total: 1,
        pages: 1,
      }),
    );

    expect(await screen.findAllByText("Acme Australia")).not.toHaveLength(0);
    expect(
      screen.getByRole("link", { name: "Create company" }),
    ).toHaveAttribute("href", "/companies/new");
    expect(screen.getAllByRole("link", { name: /edit/i })[0]).toHaveAttribute(
      "href",
      "/companies/company-1/edit",
    );
  });

  it("renders an empty state and applies search input", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ items: [], page: 1, pageSize: 20, total: 0, pages: 0 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityList entity="contacts" />);
    expect(
      await screen.findByRole("heading", { name: "No contacts found" }),
    ).toBeVisible();

    fireEvent.change(screen.getByLabelText("Search contacts"), {
      target: { value: "Jordan Lee" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("search=Jordan+Lee");
  });

  it("shows a recoverable error state", async () => {
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
      .mockResolvedValueOnce(
        jsonResponse({ items: [], page: 1, pageSize: 20, total: 0, pages: 0 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityList entity="tasks" />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Persistence is unavailable.");

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No tasks found" }),
    ).toBeVisible();
  });
});
