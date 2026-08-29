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
            id: "contact-1",
            firstName: "Avery",
            lastName: "Stone",
            email: "avery@acme.example",
          },
        ]),
      )
      .mockImplementationOnce(() =>
        response([
          {
            id: "opportunity-1",
            name: "Acme expansion",
            companyName: "Acme",
            stage: "proposal",
          },
        ]),
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

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(screen.getByRole("link", { name: /Avery Stone/i })).toHaveAttribute(
      "href",
      "/contacts/contact-1",
    );
    expect(
      screen.getByRole("link", { name: /Acme Technology/i }),
    ).toHaveAttribute("href", "/companies/company-1");
    expect(
      screen.getByRole("link", { name: /Acme expansion/i }),
    ).toHaveAttribute("href", "/opportunities/opportunity-1");
    expect(
      screen.getByRole("link", { name: /Acme workshop/i }),
    ).toHaveAttribute("href", "/interactions/interaction-1");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("search=Acme");
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("/api/v1/contacts");
    expect(screen.getByText(/does not generate an AI answer/i)).toBeVisible();
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
          safeMessage: "Authorised RevenueOS evidence only.",
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

    expect(screen.getByRole("tab", { name: "Ask RevenueOS" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(await screen.findByText("About: Acme")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Ask RevenueOS" })).toHaveValue(
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
            safeMessage: "Authorised RevenueOS evidence only.",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<CoreSearch />);
    const searchTab = screen.getByRole("tab", { name: "Search" });
    searchTab.focus();
    fireEvent.keyDown(searchTab, { key: "ArrowRight" });
    const askTab = screen.getByRole("tab", { name: "Ask RevenueOS" });
    await waitFor(() => expect(askTab).toHaveFocus());
    expect(askTab).toHaveAttribute("aria-selected", "true");
    expect(
      await screen.findByText("About: Your accessible sales work"),
    ).toBeVisible();
  });
});
