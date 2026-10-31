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
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes("/api/v1/crm/members")
          ? Promise.resolve(
              jsonResponse([
                { userId: "user-1", displayName: "Alex Morgan", active: true },
              ]),
            )
          : new Promise<Response>((resolve) => {
              resolveFetch = resolve;
            }),
      ),
    );

    render(<BusinessEntityList entity="companies" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading accounts");

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
    expect(screen.getAllByText("Alex Morgan")).not.toHaveLength(0);
    expect(
      screen.getByRole("link", { name: "Create account" }),
    ).toHaveAttribute("href", "/companies/new");
    expect(screen.getAllByRole("link", { name: /edit/i })[0]).toHaveAttribute(
      "href",
      "/companies/company-1/edit",
    );
  });

  it("renders an empty state and applies search input", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        String(input).includes("/api/v1/crm/members")
          ? jsonResponse([])
          : jsonResponse({
              items: [],
              page: 1,
              pageSize: 20,
              total: 0,
              pages: 0,
            }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityList entity="contacts" />);
    expect(
      await screen.findByRole("heading", { name: "No people found" }),
    ).toBeVisible();

    fireEvent.change(screen.getByLabelText("Search people"), {
      target: { value: "Jordan Lee" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("search=Jordan+Lee"),
      ),
    ).toBe(true);
  });

  it("shows active, unassigned, inactive and unavailable task assignees", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input).includes("/api/v1/crm/members")) {
        return Promise.resolve(
          jsonResponse([
            {
              userId: "user-active",
              displayName: "Alex Morgan",
              active: true,
            },
            {
              userId: "user-inactive",
              displayName: "Casey Nguyen",
              active: false,
            },
          ]),
        );
      }
      return Promise.resolve(
        jsonResponse({
          items: [
            {
              id: "task-active",
              title: "Active owner task",
              assignedUserId: "user-active",
              status: "open",
              priority: "medium",
              dueAt: null,
            },
            {
              id: "task-unassigned",
              title: "Unassigned task",
              assignedUserId: null,
              status: "open",
              priority: "low",
              dueAt: null,
            },
            {
              id: "task-inactive",
              title: "Inactive owner task",
              assignedUserId: "user-inactive",
              status: "in_progress",
              priority: "high",
              dueAt: null,
            },
            {
              id: "task-unavailable",
              title: "Unavailable owner task",
              assignedUserId: "user-unavailable",
              status: "open",
              priority: "medium",
              dueAt: null,
            },
          ],
          page: 1,
          pageSize: 20,
          total: 4,
          pages: 1,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityList entity="tasks" />);

    expect(await screen.findAllByText("Alex Morgan")).not.toHaveLength(0);
    expect(screen.getAllByText("Unassigned")).not.toHaveLength(0);
    expect(screen.getAllByText("Casey Nguyen (inactive)")).not.toHaveLength(0);
    expect(
      screen.getAllByText("Inactive or unavailable member"),
    ).not.toHaveLength(0);
  });

  it("shows a recoverable error state", async () => {
    let taskRequests = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input).includes("/api/v1/crm/members")) {
        return Promise.resolve(jsonResponse([]));
      }
      taskRequests += 1;
      return Promise.resolve(
        taskRequests === 1
          ? jsonResponse(
              {
                code: "persistence_unavailable",
                message: "Persistence is unavailable.",
                requestId: "request-1",
              },
              503,
            )
          : jsonResponse({
              items: [],
              page: 1,
              pageSize: 20,
              total: 0,
              pages: 0,
            }),
      );
    });
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
