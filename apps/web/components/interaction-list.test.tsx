import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InteractionList } from "@/components/interaction-list";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
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

const contactPage = {
  items: [
    {
      id: "contact-1",
      companyId: "company-1",
      firstName: "Jordan",
      lastName: "Lee",
    },
  ],
  page: 1,
  pageSize: 100,
  total: 1,
  pages: 1,
};

describe("InteractionList", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders an account-first directory with deterministic account navigation", async () => {
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
      "Loading conversations",
    );
    expect(
      await screen.findByRole("heading", { name: "Account conversations" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Acme Australia" }),
    ).toBeVisible();
    expect(
      screen.getAllByRole("link", { name: "Acme Australia" })[0],
    ).toHaveAttribute(
      "href",
      "/conversations/accounts/company-1#conversations",
    );
    expect(
      screen.getByRole("link", { name: "Acme discovery" }),
    ).toHaveAttribute("href", "/conversations/interaction-1");
    expect(
      screen.getByRole("link", { name: "View conversations and notes" }),
    ).toHaveAttribute(
      "href",
      "/conversations/accounts/company-1#conversations",
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
      await screen.findByRole("heading", { name: "No conversations found" }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Search conversations"), {
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

  it("hydrates accounts outside the first company page and appends filtered result pages", async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    const firstFilteredPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "phone-101",
          companyId: "company-101",
          meetingId: null,
          interactionType: "phone_call",
          title: "First paged call",
        },
      ],
      total: 2,
      pages: 2,
    };
    const secondFilteredPage = {
      ...firstFilteredPage,
      items: [
        {
          ...firstFilteredPage.items[0],
          id: "phone-102",
          companyId: "company-102",
          title: "Second paged call",
        },
      ],
      page: 2,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/interactions")) {
        if (!path.includes("interactionType=phone_call")) {
          return Promise.resolve(jsonResponse(emptyPage));
        }
        return Promise.resolve(
          jsonResponse(
            path.includes("page=2") ? secondFilteredPage : firstFilteredPage,
          ),
        );
      }
      if (path.includes("/companies/company-101")) {
        return Promise.resolve(
          jsonResponse({
            id: "company-101",
            name: "Outside Page One",
            archivedAt: null,
          }),
        );
      }
      if (path.includes("/companies/company-102")) {
        return Promise.resolve(
          jsonResponse(
            {
              code: "persistence_unavailable",
              message: "Companies are temporarily unavailable.",
              requestId: "request-page-two",
            },
            503,
          ),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", { name: "No conversations found" }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Filter by type"), {
      target: { value: "phone_call" },
    });

    expect(
      await screen.findByRole("heading", { name: "Outside Page One" }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/v1/companies/company-101"),
      ),
    ).toBe(true);
    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );

    expect(
      await screen.findByRole("link", { name: "Second paged call" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Linked account" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Outside Page One" }),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) => {
        const path = String(input);
        return (
          path.includes("/api/v1/interactions?") &&
          path.includes("page=2") &&
          path.includes("interactionType=phone_call")
        );
      }),
    ).toBe(true);
  });

  it("preserves fast page-two context when page-one enrichment finishes later", async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    const firstPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "slow-context-conversation",
          companyId: "company-slow",
          title: "Slow context conversation",
        },
      ],
      total: 2,
      pages: 2,
    };
    const secondPage = {
      ...firstPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "fast-context-conversation",
          companyId: "company-fast",
          title: "Fast context conversation",
        },
      ],
      page: 2,
    };
    const slowCompany = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          return Promise.resolve(
            jsonResponse(path.includes("page=2") ? secondPage : firstPage),
          );
        }
        if (path.includes("?pageSize=100")) {
          return Promise.resolve(jsonResponse(emptyPage));
        }
        if (path.includes("/companies/company-slow")) {
          return slowCompany.promise;
        }
        if (path.includes("/companies/company-fast")) {
          return Promise.resolve(
            jsonResponse({
              id: "company-fast",
              name: "Fast Account",
              archivedAt: null,
            }),
          );
        }
        return Promise.resolve(jsonResponse(emptyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByRole("link", { name: "Slow context conversation" }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Fast Account" }),
    ).toBeVisible();

    slowCompany.resolve(
      jsonResponse({
        id: "company-slow",
        name: "Slow Account",
        archivedAt: null,
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "Slow Account" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Fast Account" })).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("reloads when the current search is explicitly submitted again", async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    let interactionReads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          interactionReads += 1;
          return Promise.resolve(
            jsonResponse({
              ...interactionPage,
              items: [
                {
                  ...interactionPage.items[0],
                  id: "same-query-" + interactionReads,
                  companyId: null,
                  title:
                    interactionReads === 1
                      ? "Original conversation"
                      : "Reloaded conversation",
                },
              ],
            }),
          );
        }
        return Promise.resolve(jsonResponse(emptyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", { name: "Original conversation" }),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(
      await screen.findByRole("heading", { name: "Reloaded conversation" }),
    ).toBeVisible();
    expect(interactionReads).toBe(2);
    expect(
      screen.queryByRole("heading", { name: "Original conversation" }),
    ).not.toBeInTheDocument();
  });

  it("ignores a stale pagination success after the active filter changes", async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    const firstPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "original-filter-conversation",
          companyId: null,
          title: "Original filter conversation",
        },
      ],
      total: 2,
      pages: 2,
    };
    const filteredPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "active-filter-conversation",
          companyId: null,
          interactionType: "phone_call",
          title: "Active filter conversation",
        },
      ],
    };
    const stalePage = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          if (path.includes("page=2")) return stalePage.promise;
          if (path.includes("interactionType=phone_call")) {
            return Promise.resolve(jsonResponse(filteredPage));
          }
          return Promise.resolve(jsonResponse(firstPage));
        }
        return Promise.resolve(jsonResponse(emptyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", {
        name: "Original filter conversation",
      }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );
    fireEvent.change(screen.getByLabelText("Filter by type"), {
      target: { value: "phone_call" },
    });
    expect(
      await screen.findByRole("heading", {
        name: "Active filter conversation",
      }),
    ).toBeVisible();

    await act(async () => {
      stalePage.resolve(
        jsonResponse({
          ...firstPage,
          page: 2,
          items: [
            {
              ...interactionPage.items[0],
              id: "stale-page-conversation",
              companyId: null,
              title: "Stale page conversation",
            },
          ],
        }),
      );
      await stalePage.promise;
    });

    expect(
      screen.getByRole("heading", { name: "Active filter conversation" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Stale page conversation" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Load more conversations" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("ignores a stale pagination failure after the active filter changes", async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    const firstPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "failure-filter-conversation",
          companyId: null,
          title: "Failure filter conversation",
        },
      ],
      total: 2,
      pages: 2,
    };
    const filteredPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "failure-active-conversation",
          companyId: null,
          interactionType: "phone_call",
          title: "Failure active conversation",
        },
      ],
    };
    const stalePage = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          if (path.includes("page=2")) return stalePage.promise;
          if (path.includes("interactionType=phone_call")) {
            return Promise.resolve(jsonResponse(filteredPage));
          }
          return Promise.resolve(jsonResponse(firstPage));
        }
        return Promise.resolve(jsonResponse(emptyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", {
        name: "Failure filter conversation",
      }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );
    fireEvent.change(screen.getByLabelText("Filter by type"), {
      target: { value: "phone_call" },
    });
    expect(
      await screen.findByRole("heading", {
        name: "Failure active conversation",
      }),
    ).toBeVisible();

    await act(async () => {
      stalePage.resolve(
        jsonResponse(
          {
            code: "persistence_unavailable",
            message: "The stale page failed.",
            requestId: "request-stale-page",
          },
          503,
        ),
      );
      await stalePage.promise;
    });

    expect(
      screen.getByRole("heading", {
        name: "Failure active conversation",
      }),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("ignores a stale initial failure after the active filter changes", async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    const filteredPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "current-filter-conversation",
          companyId: null,
          interactionType: "phone_call",
          title: "Current filter conversation",
        },
      ],
    };
    const staleInitial = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          if (path.includes("interactionType=phone_call")) {
            return Promise.resolve(jsonResponse(filteredPage));
          }
          return staleInitial.promise;
        }
        return Promise.resolve(jsonResponse(emptyPage));
      }),
    );

    render(<InteractionList />);
    fireEvent.change(screen.getByLabelText("Filter by type"), {
      target: { value: "phone_call" },
    });
    expect(
      await screen.findByRole("heading", {
        name: "Current filter conversation",
      }),
    ).toBeVisible();

    await act(async () => {
      staleInitial.resolve(
        jsonResponse(
          {
            code: "persistence_unavailable",
            message: "The stale initial request failed.",
            requestId: "request-stale-initial",
          },
          503,
        ),
      );
      await staleInitial.promise;
    });

    expect(
      screen.getByRole("heading", {
        name: "Current filter conversation",
      }),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not let optional page context block later conversation pages", async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    const firstPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "first-page-conversation",
          companyId: null,
          title: "First page conversation",
        },
      ],
      total: 3,
      pages: 3,
    };
    const secondPage = {
      ...firstPage,
      page: 2,
      items: [
        {
          ...interactionPage.items[0],
          id: "second-page-conversation",
          companyId: "company-slow-page",
          title: "Second page conversation",
        },
      ],
    };
    const thirdPage = {
      ...firstPage,
      page: 3,
      items: [
        {
          ...interactionPage.items[0],
          id: "third-page-conversation",
          companyId: null,
          title: "Third page conversation",
        },
      ],
    };
    const slowCompany = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          if (path.includes("page=3")) {
            return Promise.resolve(jsonResponse(thirdPage));
          }
          if (path.includes("page=2")) {
            return Promise.resolve(jsonResponse(secondPage));
          }
          return Promise.resolve(jsonResponse(firstPage));
        }
        if (path.includes("?pageSize=100")) {
          return Promise.resolve(jsonResponse(emptyPage));
        }
        if (path.includes("/companies/company-slow-page")) {
          return slowCompany.promise;
        }
        return Promise.resolve(jsonResponse(emptyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", { name: "First page conversation" }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );
    expect(
      await screen.findByRole("link", { name: "Second page conversation" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Linked account" }),
    ).toBeVisible();

    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Third page conversation" }),
    ).toBeVisible();

    slowCompany.resolve(
      jsonResponse({
        id: "company-slow-page",
        name: "Eventually loaded account",
        archivedAt: null,
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Eventually loaded account",
      }),
    ).toBeVisible();
  });

  it("keeps conversations usable when context collections and exact lookups fail", async () => {
    const resilientPage = {
      ...interactionPage,
      items: [
        interactionPage.items[0],
        {
          ...interactionPage.items[0],
          id: "general-1",
          companyId: null,
          contactId: "contact-missing",
          meetingId: null,
          interactionType: "phone_call",
          title: "Unassigned call",
        },
      ],
      total: 2,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/interactions")) {
        return Promise.resolve(jsonResponse(resilientPage));
      }
      if (
        path.includes("/companies?pageSize=100") ||
        path.includes("/contacts?pageSize=100")
      ) {
        return Promise.resolve(
          jsonResponse(
            {
              code: "persistence_unavailable",
              message: "Context is temporarily unavailable.",
              requestId: "request-context",
            },
            503,
          ),
        );
      }
      return Promise.resolve(
        jsonResponse(
          {
            code: "not_found",
            message: "The linked record was not found.",
            requestId: "request-missing",
          },
          404,
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionList />);

    expect(
      await screen.findByRole("heading", { name: "Linked account" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Acme discovery" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Unassigned call" }),
    ).toBeVisible();
    expect(screen.getByText("Linked contact")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("hydrates valid context independently and rejects archived labels", async () => {
    const mixedPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "good-company-conversation",
          companyId: "company-good",
          title: "Known account conversation",
        },
        {
          ...interactionPage.items[0],
          id: "missing-company-conversation",
          companyId: "company-missing",
          title: "Missing account conversation",
        },
        {
          ...interactionPage.items[0],
          id: "archived-company-conversation",
          companyId: "company-archived",
          title: "Archived account conversation",
        },
        {
          ...interactionPage.items[0],
          id: "good-contact-conversation",
          companyId: null,
          contactId: "contact-good",
          interactionType: "phone_call",
          title: "Known contact call",
        },
        {
          ...interactionPage.items[0],
          id: "missing-contact-conversation",
          companyId: null,
          contactId: "contact-missing",
          interactionType: "phone_call",
          title: "Missing contact call",
        },
        {
          ...interactionPage.items[0],
          id: "archived-contact-conversation",
          companyId: null,
          contactId: "contact-archived",
          interactionType: "phone_call",
          title: "Archived contact call",
        },
      ],
      total: 6,
    };
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    const mixedFetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/interactions")) {
        return Promise.resolve(jsonResponse(mixedPage));
      }
      if (path.includes("?pageSize=100")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (path.includes("/companies/company-good")) {
        return Promise.resolve(
          jsonResponse({
            id: "company-good",
            name: "Good Account",
            archivedAt: null,
          }),
        );
      }
      if (path.includes("/companies/company-archived")) {
        return Promise.resolve(
          jsonResponse({
            id: "company-archived",
            name: "Archived Account Name",
            archivedAt: "2026-07-26T00:00:00Z",
          }),
        );
      }
      if (path.includes("/contacts/contact-good")) {
        return Promise.resolve(
          jsonResponse({
            id: "contact-good",
            companyId: null,
            firstName: "Good",
            lastName: "Contact",
            archivedAt: null,
          }),
        );
      }
      if (path.includes("/contacts/contact-archived")) {
        return Promise.resolve(
          jsonResponse({
            id: "contact-archived",
            companyId: null,
            firstName: "Archived",
            lastName: "Contact Name",
            archivedAt: "2026-07-26T00:00:00Z",
          }),
        );
      }
      if (path.includes("/contacts/contact-missing")) {
        return Promise.resolve(
          jsonResponse({
            id: "contact-from-another-request",
            companyId: null,
            firstName: "Wrong",
            lastName: "Contact Name",
            archivedAt: null,
          }),
        );
      }
      return Promise.resolve(
        jsonResponse(
          {
            code: "not_found",
            message: "The linked record was not found.",
            requestId: "request-mixed",
          },
          404,
        ),
      );
    });
    vi.stubGlobal("fetch", mixedFetchMock);

    render(<InteractionList />);

    expect(
      await screen.findByRole("heading", { name: "Good Account" }),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        mixedFetchMock.mock.calls.some(([input]) =>
          String(input).includes("/contacts/contact-good"),
        ),
      ).toBe(true),
    );
    expect(await screen.findByText("Good Contact")).toBeVisible();
    expect(
      screen.getAllByRole("heading", { name: "Linked account" }),
    ).toHaveLength(2);
    expect(screen.getAllByText("Linked contact")).toHaveLength(2);
    expect(screen.queryByText("Archived Account Name")).not.toBeInTheDocument();
    expect(screen.queryByText("Archived Contact Name")).not.toBeInTheDocument();
    expect(screen.queryByText("Wrong Contact Name")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
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
      .mockResolvedValueOnce(jsonResponse(contactPage))
      .mockResolvedValueOnce(
        jsonResponse({ ...interactionPage, items: [], total: 0, pages: 0 }),
      )
      .mockResolvedValueOnce(jsonResponse(companyPage))
      .mockResolvedValueOnce(jsonResponse(contactPage));
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionList />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Interactions are temporarily unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No conversations found" }),
    ).toBeVisible();
  });

  it("shows phone direction, contact, duration, capture and intelligence readiness", async () => {
    const phonePage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "overdue",
          title: "Overdue discovery",
          scheduledStartAt: "2025-08-01T00:00:00Z",
        },
        {
          ...interactionPage.items[0],
          id: "phone-1",
          title: "Commercial call",
          companyId: null,
          meetingId: null,
          contactId: "contact-1",
          interactionType: "phone_call",
          lifecycleStatus: "completed",
          callDirection: "outbound",
          callOutcome: "connected",
          durationSeconds: 185,
          captureMethods: ["debrief", "recording"],
          intelligenceState: "ready",
          recordingAvailable: true,
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          return Promise.resolve(jsonResponse(phonePage));
        }
        if (path.includes("/contacts")) {
          return Promise.resolve(jsonResponse(contactPage));
        }
        return Promise.resolve(jsonResponse(companyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", { name: "Commercial call" }),
    ).toBeVisible();
    expect(screen.getByText("Outbound")).toBeVisible();
    expect(screen.getByText("Jordan Lee")).toBeVisible();
    expect(screen.getByText("· 3m 5s")).toBeVisible();
    expect(screen.getByText("· Connected")).toBeVisible();
    expect(
      screen.getByText(
        "Capture: Debrief · Recording · Intelligence ready · Recording available",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open notes and follow-up" }),
    ).toHaveAttribute("href", "/conversations/phone-1#debrief");
    expect(
      screen.getByRole("heading", {
        name: "General and unassigned conversations",
      }),
    ).toBeVisible();
  });

  it("groups several conversations beneath one account instead of repeating it", async () => {
    const groupedPage = {
      ...interactionPage,
      items: [
        interactionPage.items[0],
        {
          ...interactionPage.items[0],
          id: "interaction-2",
          title: "Acme follow-up",
          briefState: "not_generated",
        },
      ],
      total: 2,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          return Promise.resolve(jsonResponse(groupedPage));
        }
        if (path.includes("/contacts")) {
          return Promise.resolve(jsonResponse(contactPage));
        }
        return Promise.resolve(jsonResponse(companyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByText("2 conversations · 1 prepared"),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: "Acme Australia 2 conversations",
      }),
    ).toHaveAttribute(
      "href",
      "/conversations/accounts/company-1#conversations",
    );
    expect(
      screen.getByRole("link", { name: "Acme Australia" }),
    ).toHaveAttribute(
      "href",
      "/conversations/accounts/company-1#conversations",
    );
    expect(
      screen.queryByRole("heading", { name: "Acme follow-up" }),
    ).not.toBeInTheDocument();
  });

  it("highlights the nearest future conversation rather than the farthest", async () => {
    const groupedPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "overdue-meeting",
          title: "Overdue discovery",
          scheduledStartAt: "2025-08-01T00:00:00Z",
        },
        {
          ...interactionPage.items[0],
          id: "far-future",
          title: "Annual review",
          scheduledStartAt: "2031-08-01T00:00:00Z",
        },
        {
          ...interactionPage.items[0],
          id: "next-meeting",
          title: "Next discovery",
          scheduledStartAt: "2030-08-01T00:00:00Z",
        },
      ],
      total: 3,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          return Promise.resolve(jsonResponse(groupedPage));
        }
        if (path.includes("/contacts")) {
          return Promise.resolve(jsonResponse(contactPage));
        }
        return Promise.resolve(jsonResponse(companyPage));
      }),
    );

    render(<InteractionList />);
    expect(await screen.findByText("Next conversation")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Next discovery" }),
    ).toHaveAttribute("href", "/conversations/next-meeting");
    expect(
      screen.queryByRole("link", { name: "Annual review" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Overdue discovery" }),
    ).not.toBeInTheDocument();
  });
});
