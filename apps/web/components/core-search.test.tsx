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

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
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
});
