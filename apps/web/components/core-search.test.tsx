import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CoreSearch } from "@/components/core-search";

function response(items: object[]) {
  return Promise.resolve(
    new Response(
      JSON.stringify({
        items,
        page: 1,
        pageSize: 6,
        total: items.length,
        pages: 1,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
}

function unavailable(message = "Search is temporarily unavailable.") {
  return Promise.resolve(
    new Response(
      JSON.stringify({
        code: "search_unavailable",
        message,
        requestId: "request-search-unavailable",
      }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    ),
  );
}

function deferred<T>() {
  let resolvePromise: ((value: T) => void) | undefined;
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });
  return {
    promise,
    resolve(value: T) {
      if (!resolvePromise)
        throw new Error("Deferred promise was not initialised.");
      resolvePromise(value);
    },
  };
}

describe("CoreSearch", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("searches only the bounded core entities and links to matching work", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() =>
        response([{ id: "company-1", name: "Acme", industry: "Technology" }]),
      )
      .mockImplementationOnce(() =>
        response([
          {
            id: "interaction-1",
            title: "Acme workshop",
            interactionType: "workshop",
            lifecycleStatus: "planned",
          },
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search your workspace" }),
      {
        target: { value: "Acme" },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      screen.getByRole("link", { name: /Acme Technology/i }),
    ).toHaveAttribute("href", "/conversations/accounts/company-1");
    expect(
      screen.getByRole("link", { name: /Acme workshop/i }),
    ).toHaveAttribute("href", "/conversations/interaction-1");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("search=Acme");
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      "/api/v1/interactions",
    );
    expect(
      fetchMock.mock.calls.some(([url]) =>
        /opportunities|contacts/.test(String(url)),
      ),
    ).toBe(false);
    expect(screen.getByText(/transcript or your private notes/i)).toBeVisible();
    expect(screen.getByRole("searchbox")).toHaveAttribute(
      "placeholder",
      "Try a conversation, private note or account",
    );
  });

  it("keeps private-note search guidance in the empty state", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => response([]))
      .mockImplementationOnce(() => response([]));
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "remembered phrase" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("No matching work found")).toBeVisible();
    expect(
      screen.getByText(
        /shorter phrase from a conversation, your private notes/i,
      ),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("keeps conversation results visible when account search is unavailable", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => unavailable())
      .mockImplementationOnce(() =>
        response([
          {
            id: "interaction-private-note",
            title: "Remembered customer detail",
            interactionType: "meeting",
            lifecycleStatus: "completed",
          },
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "remembered detail" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(
      await screen.findByRole("link", { name: /Remembered customer detail/i }),
    ).toHaveAttribute("href", "/conversations/interaction-private-note");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Account results are temporarily unavailable",
    );
    expect(screen.getByText("1 available result")).toBeVisible();
    expect(
      screen.queryByText("No matching work found"),
    ).not.toBeInTheDocument();
  });

  it("keeps account results visible when conversation search is unavailable", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() =>
        response([{ id: "company-available", name: "Acme", industry: null }]),
      )
      .mockImplementationOnce(() => unavailable());
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(
      await screen.findByRole("link", { name: /Acme Account/i }),
    ).toHaveAttribute("href", "/conversations/accounts/company-available");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Conversation results are temporarily unavailable",
    );
    expect(
      screen.queryByText("No matching work found"),
    ).not.toBeInTheDocument();
  });

  it("publishes a successful source while the other source is still pending", async () => {
    const conversations = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() =>
        response([
          { id: "company-ready", name: "Ready account", industry: null },
        ]),
      )
      .mockImplementationOnce(() => conversations.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "ready" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(
      await screen.findByRole("link", { name: /Ready account Account/i }),
    ).toHaveAttribute("href", "/conversations/accounts/company-ready");
    expect(screen.queryByText("0 available results")).not.toBeInTheDocument();
    expect(screen.getByText("1 available result")).toBeVisible();
    expect(screen.getByText("Searching conversation results…")).toHaveAttribute(
      "role",
      "status",
    );
    expect(
      screen.queryByText("No matching work found"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/temporarily unavailable/),
    ).not.toBeInTheDocument();

    conversations.resolve(await response([]));
    expect(await screen.findByText("1 result")).toBeVisible();
    expect(
      screen.queryByText("Searching conversation results"),
    ).not.toBeInTheDocument();
  });

  it("lets a changed Enter-style submission supersede an in-flight search", async () => {
    const firstCompanies = deferred<Response>();
    const firstConversations = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("search=first")) {
        return url.includes("/companies")
          ? firstCompanies.promise
          : firstConversations.promise;
      }
      if (url.includes("search=second")) {
        return url.includes("/companies")
          ? response([
              {
                id: "company-second",
                name: "Second result",
                industry: null,
              },
            ])
          : unavailable();
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    const searchbox = screen.getByRole("searchbox");
    const form = searchbox.closest("form");
    if (!form) throw new Error("Search form was not rendered.");
    fireEvent.change(searchbox, { target: { value: "first" } });
    fireEvent.submit(form);
    expect(
      await screen.findByRole("button", { name: "Searching…" }),
    ).toBeDisabled();

    fireEvent.change(searchbox, { target: { value: "second" } });
    expect(screen.getByRole("button", { name: "Search" })).toBeEnabled();
    fireEvent.submit(form);
    expect(
      await screen.findByRole("link", { name: /Second result Account/i }),
    ).toHaveAttribute("href", "/conversations/accounts/company-second");
    expect(screen.getByText("Results for “second”")).toBeVisible();

    firstCompanies.resolve(
      await response([
        { id: "company-first", name: "Stale first result", industry: null },
      ]),
    );
    firstConversations.resolve(await unavailable());

    await waitFor(() =>
      expect(
        screen.queryByRole("link", { name: /Stale first result/i }),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Results for “second”")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("does not duplicate the same active search through form submission", async () => {
    const companies = deferred<Response>();
    const conversations = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => companies.promise)
      .mockImplementationOnce(() => conversations.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    const searchbox = screen.getByRole("searchbox");
    const form = searchbox.closest("form");
    if (!form) throw new Error("Search form was not rendered.");
    fireEvent.change(searchbox, { target: { value: "same search" } });
    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByText("Search in progress")).toBeVisible();
    expect(screen.queryByText("0 available results")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No matching work found"),
    ).not.toBeInTheDocument();
    companies.resolve(await response([]));
    conversations.resolve(await response([]));
    expect(await screen.findByText("No matching work found")).toBeVisible();
  });

  it("invalidates an in-flight search when an invalid query is submitted", async () => {
    const companies = deferred<Response>();
    const conversations = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => companies.promise)
      .mockImplementationOnce(() => conversations.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    const searchbox = screen.getByRole("searchbox");
    const form = searchbox.closest("form");
    if (!form) throw new Error("Search form was not rendered.");
    fireEvent.change(searchbox, { target: { value: "valid search" } });
    fireEvent.submit(form);
    fireEvent.change(searchbox, { target: { value: "x" } });
    fireEvent.submit(form);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "at least two characters",
    );
    expect(screen.getByRole("button", { name: "Search" })).toBeEnabled();

    companies.resolve(
      await response([
        { id: "company-stale", name: "Stale result", industry: null },
      ]),
    );
    conversations.resolve(await response([]));

    await waitFor(() =>
      expect(
        screen.queryByRole("link", { name: /Stale result/i }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByText(
        "Start with the conversation or relationship you want to remember. Recent work remains on Home and in conversation history.",
      ),
    ).toBeVisible();
  });

  it("shows the recoverable search error without a false empty state when both sources fail", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => unavailable("Do not expose account error."))
      .mockImplementationOnce(() =>
        unavailable("Do not expose conversation error."),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Search could not be completed. Please try again.",
    );
    expect(
      screen.queryByText("No matching work found"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Do not expose/)).not.toBeInTheDocument();
  });

  it("clears a partial-results warning after the next complete search", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => unavailable())
      .mockImplementationOnce(() => response([]))
      .mockImplementationOnce(() => response([]))
      .mockImplementationOnce(() => response([]));
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "first search" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Account results are temporarily unavailable",
    );
    expect(screen.getByText("0 available results")).toBeVisible();
    expect(
      screen.queryByText("No matching work found"),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "second search" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("No matching work found")).toBeVisible();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("does not send a one-character search", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<CoreSearch />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "A" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "at least two characters",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps deterministic Search separate while opening Ask in explicit scope", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          enabled: true,
          scope: { type: "account", id: "company-1", label: "Acme" },
          supportedScopes: ["opportunity", "account", "workspace"],
          retainedHistory: false,
          publicWebResearch: false,
          actionExecution: false,
          maxQuestionCharacters: 1000,
          maxSources: 12,
          safeMessage: "Authorised Oryntela evidence only.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <CoreSearch
        initialMode="ask"
        scopeType="account"
        scopeId="company-1"
        initialQuestion="What changed recently?"
      />,
    );

    expect(screen.getByRole("tab", { name: "Ask Oryntela" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(await screen.findByText("About: Acme")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Ask Oryntela" })).toHaveValue(
      "What changed recently?",
    );
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "scopeType=account&scopeId=company-1",
    );

    fireEvent.click(screen.getByRole("tab", { name: "Search" }));
    expect(
      screen.getByRole("searchbox", { name: "Search your workspace" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("supports arrow-key navigation between Search and Ask tabs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            enabled: true,
            scope: {
              type: "workspace",
              id: null,
              label: "Your accessible sales work",
            },
            supportedScopes: ["opportunity", "account", "workspace"],
            retainedHistory: false,
            publicWebResearch: false,
            actionExecution: false,
            maxQuestionCharacters: 1000,
            maxSources: 12,
            safeMessage: "Authorised Oryntela evidence only.",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<CoreSearch />);
    const searchTab = screen.getByRole("tab", { name: "Search" });
    searchTab.focus();
    fireEvent.keyDown(searchTab, { key: "ArrowRight" });
    const askTab = screen.getByRole("tab", { name: "Ask Oryntela" });
    await waitFor(() => expect(askTab).toHaveFocus());
    expect(askTab).toHaveAttribute("aria-selected", "true");
    expect(
      await screen.findByText("About: Your accessible sales work"),
    ).toBeVisible();
  });
});
