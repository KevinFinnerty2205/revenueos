import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountConversationPanel } from "@/components/account-conversation-panel";

function jsonResponse(body: object): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
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
    expect(screen.getByText("Jordan Lee")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open live workspace" }),
    ).toHaveAttribute("href", "/conversations/interaction-1/workspace");
    expect(
      screen.getByRole("link", { name: "Add conversation" }),
    ).toHaveAttribute("href", "/conversations/new?companyId=company%2Fone");
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("companyId=company%2Fone"),
      ),
    ).toBe(true);
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
    expect(screen.getByText("Casey Outside Page")).toBeVisible();
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
    expect(screen.getByText("Morgan Later Page")).toBeVisible();
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
