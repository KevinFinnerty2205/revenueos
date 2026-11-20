import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountConversationPanel } from "@/components/account-conversation-panel";

function jsonResponse(body: object): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, message: string): Response {
  return new Response(
    JSON.stringify({
      code: "contact_enrichment_failed",
      message,
      requestId: "contact-request-private",
    }),
    {
      status,
      headers: { "Content-Type": "application/json" },
    },
  );
}

const interactionPage = {
  items: [
    {
      id: "interaction-1",
      organisationId: "organisation-1",
      companyId: "company/one",
      opportunityId: null,
      contactId: "contact-1",
      meetingId: null,
      interactionType: "phone_call",
      lifecycleStatus: "planned",
      title: "Account discovery call",
      scheduledStartAt: "2030-08-01T00:00:00Z",
      scheduledEndAt: null,
      actualStartAt: null,
      actualEndAt: null,
      timezone: "Australia/Sydney",
      creationOrigin: "manual",
      callDirection: "outbound",
      callOutcome: null,
      durationSeconds: null,
      captureMethods: [],
      intelligenceState: "not_ready",
      recordingAvailable: false,
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

const contactPage = {
  items: [
    {
      id: "contact-1",
      companyId: "company/one",
      firstName: "Jordan",
      lastName: "Lee",
      archivedAt: null,
    },
  ],
  page: 1,
  pageSize: 100,
  total: 1,
  pages: 1,
};

describe("AccountConversationPanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads only the account conversations and links to the live workspace", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        jsonResponse(
          String(input).includes("/contacts") ? contactPage : interactionPage,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountConversationPanel companyId="company/one" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading account conversations",
    );
    expect(
      await screen.findByRole("heading", { name: "Account discovery call" }),
    ).toBeVisible();
    expect(await screen.findByText("Jordan Lee")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open live workspace" }),
    ).toHaveAttribute("href", "/conversations/interaction-1?view=capture");
    expect(
      screen.getByRole("link", { name: "Add conversation" }),
    ).toHaveAttribute("href", "/conversations/new?companyId=company%2Fone");
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("companyId=company%2Fone"),
      ),
    ).toBe(true);
  });

  it("keeps account conversations available when the contact list is unavailable", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/api/v1/interactions?")) {
        return Promise.resolve(jsonResponse(interactionPage));
      }
      if (path.includes("/api/v1/contacts/contact-1")) {
        return Promise.resolve(jsonResponse(contactPage.items[0]));
      }
      return Promise.resolve(
        errorResponse(503, "Private contact list failure details"),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountConversationPanel companyId="company/one" />);

    expect(
      await screen.findByRole("heading", { name: "Account discovery call" }),
    ).toBeVisible();
    expect(await screen.findByText("Jordan Lee")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Private contact list failure details"),
    ).not.toBeInTheDocument();
  });

  it("uses a safe fallback when an exact contact lookup returns 404", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/api/v1/interactions?")) {
        return Promise.resolve(jsonResponse(interactionPage));
      }
      if (path.includes("/api/v1/contacts/contact-1")) {
        return Promise.resolve(
          errorResponse(404, "Private contact contact-1 lookup details"),
        );
      }
      return Promise.resolve(
        jsonResponse({ ...contactPage, items: [], total: 0, pages: 0 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountConversationPanel companyId="company/one" />);

    expect(
      await screen.findByRole("heading", { name: "Account discovery call" }),
    ).toBeVisible();
    expect(await screen.findByText("Linked contact")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Private contact contact-1 lookup details"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("contact-1")).not.toBeInTheDocument();
  });

  it("rejects cross-account and archived contact enrichment", async () => {
    const scopedPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-cross-account",
          contactId: "contact-cross-account",
          title: "Cross-account contact call",
        },
        {
          ...interactionPage.items[0],
          id: "interaction-archived",
          contactId: "contact-archived",
          title: "Archived contact call",
        },
      ],
      total: 2,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/api/v1/interactions?")) {
        return Promise.resolve(jsonResponse(scopedPage));
      }
      if (path.includes("/api/v1/contacts/contact-cross-account")) {
        return Promise.resolve(
          jsonResponse({
            ...contactPage.items[0],
            id: "contact-cross-account",
            companyId: "company-two",
            firstName: "Wrong",
            lastName: "Account",
          }),
        );
      }
      if (path.includes("/api/v1/contacts/contact-archived")) {
        return Promise.resolve(
          jsonResponse({
            ...contactPage.items[0],
            id: "contact-archived",
            firstName: "Archived",
            lastName: "Person",
            archivedAt: "2026-11-01T00:00:00Z",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({ ...contactPage, items: [], total: 0, pages: 0 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountConversationPanel companyId="company/one" />);

    expect(
      await screen.findByRole("heading", {
        name: "Cross-account contact call",
      }),
    ).toBeVisible();
    expect(
      await screen.findByRole("heading", { name: "Archived contact call" }),
    ).toBeVisible();
    expect(await screen.findAllByText("Linked contact")).toHaveLength(2);
    expect(screen.queryByText("Wrong Account")).not.toBeInTheDocument();
    expect(screen.queryByText("Archived Person")).not.toBeInTheDocument();
  });

  it("does not carry a contact label into a different account", async () => {
    const otherAccountPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-other-account",
          companyId: "company-two",
          title: "Other account call",
        },
      ],
    };
    let resolveOtherAccountPage: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (
        path.includes("/api/v1/interactions?") &&
        path.includes("companyId=company-two")
      ) {
        return new Promise<Response>((resolve) => {
          resolveOtherAccountPage = resolve;
        });
      }
      if (path.includes("/api/v1/interactions?")) {
        return Promise.resolve(jsonResponse(interactionPage));
      }
      if (path.includes("/api/v1/contacts/contact-1")) {
        return Promise.resolve(
          errorResponse(404, "Private stale contact lookup details"),
        );
      }
      return Promise.resolve(
        jsonResponse(
          path.includes("companyId=company-two")
            ? { ...contactPage, items: [], total: 0, pages: 0 }
            : contactPage,
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <AccountConversationPanel companyId="company/one" />,
    );
    expect(await screen.findByText("Jordan Lee")).toBeVisible();

    rerender(<AccountConversationPanel companyId="company-two" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading account conversations",
    );
    expect(
      screen.queryByRole("heading", { name: "Account discovery call" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Jordan Lee")).not.toBeInTheDocument();
    await waitFor(() => expect(resolveOtherAccountPage).toBeTypeOf("function"));
    await act(async () => {
      resolveOtherAccountPage?.(jsonResponse(otherAccountPage));
    });

    expect(
      await screen.findByRole("heading", { name: "Other account call" }),
    ).toBeVisible();
    expect(await screen.findByText("Linked contact")).toBeVisible();
    expect(screen.queryByText("Jordan Lee")).not.toBeInTheDocument();
  });

  it("clears the previous account when the next interaction page fails", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (
        path.includes("/api/v1/interactions?") &&
        path.includes("companyId=company-two")
      ) {
        return Promise.resolve(
          errorResponse(
            503,
            "Account conversations are temporarily unavailable",
          ),
        );
      }
      if (path.includes("/api/v1/interactions?")) {
        return Promise.resolve(jsonResponse(interactionPage));
      }
      return Promise.resolve(jsonResponse(contactPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <AccountConversationPanel companyId="company/one" />,
    );
    expect(await screen.findByText("Jordan Lee")).toBeVisible();

    rerender(<AccountConversationPanel companyId="company-two" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Account conversations are temporarily unavailable",
    );
    expect(
      screen.queryByRole("heading", { name: "Account discovery call" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Jordan Lee")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
  });

  it("ignores an in-flight pagination response after the account changes", async () => {
    const accountAFirstPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-account-a-one",
          companyId: "company-a",
          contactId: "contact-account-a-one",
          title: "Account A first call",
        },
      ],
      total: 2,
      pages: 2,
    };
    const accountASecondPage = {
      ...accountAFirstPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-account-a-two",
          companyId: "company-a",
          contactId: "contact-account-a-two",
          title: "Stale account A call",
        },
      ],
      page: 2,
    };
    const accountBPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-account-b",
          companyId: "company-b",
          contactId: "contact-account-b",
          title: "Account B call",
        },
      ],
    };
    let resolveAccountASecondPage: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (
        path.includes("/api/v1/interactions?") &&
        path.includes("companyId=company-a") &&
        path.includes("page=2")
      ) {
        return new Promise<Response>((resolve) => {
          resolveAccountASecondPage = resolve;
        });
      }
      if (path.includes("/api/v1/interactions?")) {
        return Promise.resolve(
          jsonResponse(
            path.includes("companyId=company-b")
              ? accountBPage
              : accountAFirstPage,
          ),
        );
      }
      if (path.includes("companyId=company-b")) {
        return Promise.resolve(
          jsonResponse({
            ...contactPage,
            items: [
              {
                ...contactPage.items[0],
                id: "contact-account-b",
                companyId: "company-b",
                firstName: "Account B",
                lastName: "Person",
              },
            ],
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          ...contactPage,
          items: [
            {
              ...contactPage.items[0],
              id: "contact-account-a-one",
              companyId: "company-a",
              firstName: "Account A",
              lastName: "Person",
            },
          ],
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <AccountConversationPanel companyId="company-a" />,
    );
    expect(await screen.findByText("Account A Person")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );
    await waitFor(() =>
      expect(resolveAccountASecondPage).toBeTypeOf("function"),
    );

    rerender(<AccountConversationPanel companyId="company-b" />);
    expect(
      await screen.findByRole("heading", { name: "Account B call" }),
    ).toBeVisible();
    expect(await screen.findByText("Account B Person")).toBeVisible();

    await act(async () => {
      resolveAccountASecondPage?.(jsonResponse(accountASecondPage));
      await new Promise((resolve) => globalThis.setTimeout(resolve, 0));
    });

    expect(
      screen.queryByRole("heading", { name: "Stale account A call" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Account A Person")).not.toBeInTheDocument();
    expect(screen.getByText("Account B Person")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps successful exact contact enrichment when another lookup fails", async () => {
    const mixedPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-known",
          contactId: "contact-known",
          title: "Known contact call",
        },
        {
          ...interactionPage.items[0],
          id: "interaction-missing",
          contactId: "contact-missing",
          title: "Missing contact call",
        },
      ],
      total: 2,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/api/v1/interactions?")) {
        return Promise.resolve(jsonResponse(mixedPage));
      }
      if (path.includes("/api/v1/contacts/contact-known")) {
        return Promise.resolve(
          jsonResponse({
            ...contactPage.items[0],
            id: "contact-known",
            firstName: "Known",
            lastName: "Person",
          }),
        );
      }
      if (path.includes("/api/v1/contacts/contact-missing")) {
        return Promise.resolve(
          errorResponse(503, "Private second lookup failure"),
        );
      }
      return Promise.resolve(
        jsonResponse({ ...contactPage, items: [], total: 0, pages: 0 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountConversationPanel companyId="company/one" />);

    expect(await screen.findByText("Known Person")).toBeVisible();
    expect(await screen.findByText("Linked contact")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Private second lookup failure"),
    ).not.toBeInTheDocument();
  });

  it("hydrates contacts outside the first page and appends more account conversations", async () => {
    const firstPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-101",
          contactId: "contact-101",
          title: "First account call",
        },
      ],
      total: 101,
      pages: 2,
    };
    const secondPage = {
      ...firstPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-102",
          contactId: "contact-102",
          title: "Later account call",
        },
      ],
      page: 2,
    };
    const emptyContactPage = {
      ...contactPage,
      items: [],
      total: 0,
      pages: 0,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/interactions")) {
        return Promise.resolve(
          jsonResponse(path.includes("page=2") ? secondPage : firstPage),
        );
      }
      if (path.includes("/contacts/contact-101")) {
        return Promise.resolve(
          jsonResponse({
            id: "contact-101",
            companyId: "company/one",
            firstName: "Casey",
            lastName: "Outside Page",
            archivedAt: null,
          }),
        );
      }
      if (path.includes("/contacts/contact-102")) {
        return Promise.resolve(
          jsonResponse({
            id: "contact-102",
            companyId: "company/one",
            firstName: "Morgan",
            lastName: "Later Page",
            archivedAt: null,
          }),
        );
      }
      return Promise.resolve(jsonResponse(emptyContactPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountConversationPanel companyId="company/one" />);
    expect(
      await screen.findByRole("heading", { name: "First account call" }),
    ).toBeVisible();
    expect(await screen.findByText("Casey Outside Page")).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/v1/contacts/contact-101"),
      ),
    ).toBe(true);

    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Later account call" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "First account call" }),
    ).toBeVisible();
    expect(await screen.findByText("Morgan Later Page")).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) => {
        const path = String(input);
        return (
          path.includes("/api/v1/interactions?") &&
          path.includes("page=2") &&
          path.includes("companyId=company%2Fone")
        );
      }),
    ).toBe(true);
  });

  it("appends a required page when its optional contact lookup fails", async () => {
    const firstPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "interaction-page-one",
          contactId: "contact-page-one",
          title: "First resilient call",
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
          id: "interaction-page-two",
          contactId: "contact-page-two",
          title: "Second resilient call",
        },
      ],
      page: 2,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/api/v1/interactions?")) {
        return Promise.resolve(
          jsonResponse(path.includes("page=2") ? secondPage : firstPage),
        );
      }
      if (path.includes("/api/v1/contacts/contact-page-one")) {
        return Promise.resolve(
          jsonResponse({
            ...contactPage.items[0],
            id: "contact-page-one",
            firstName: "First",
            lastName: "Person",
          }),
        );
      }
      if (path.includes("/api/v1/contacts/contact-page-two")) {
        return Promise.resolve(
          errorResponse(503, "Private page-two contact failure"),
        );
      }
      return Promise.resolve(
        jsonResponse({ ...contactPage, items: [], total: 0, pages: 0 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountConversationPanel companyId="company/one" />);
    expect(await screen.findByText("First Person")).toBeVisible();

    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Second resilient call" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "First resilient call" }),
    ).toBeVisible();
    expect(await screen.findByText("Linked contact")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Private page-two contact failure"),
    ).not.toBeInTheDocument();
  });

  it("presents a useful empty account history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          jsonResponse(
            String(input).includes("/contacts")
              ? { ...contactPage, items: [], total: 0, pages: 0 }
              : { ...interactionPage, items: [], total: 0, pages: 0 },
          ),
        ),
      ),
    );

    render(<AccountConversationPanel companyId="company-1" />);
    expect(
      await screen.findByRole("heading", {
        name: "No account conversations yet",
      }),
    ).toBeVisible();
  });

  it("shows a safe error and retries without losing the account scope", async () => {
    let shouldFail = true;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (shouldFail)
        return Promise.reject(new Error("Temporarily unavailable"));
      return Promise.resolve(
        jsonResponse(
          String(input).includes("/contacts")
            ? { ...contactPage, items: [], total: 0, pages: 0 }
            : { ...interactionPage, items: [], total: 0, pages: 0 },
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountConversationPanel companyId="company-1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Oryntela could not reach the service",
    );
    shouldFail = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "No account conversations yet" }),
      ).toBeVisible(),
    );
  });
});
