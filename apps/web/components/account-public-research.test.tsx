import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountPublicResearch } from "@/components/account-public-research";

const organisationId = "organisation-1";

vi.mock("@/components/verified-organisation-context", () => ({
  useVerifiedOrganisation: () => ({
    status: "available",
    organisationId,
  }),
}));

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function research(companyId: string, targetId: string) {
  return {
    organisationId,
    targetId,
    companyId,
    updatedAt: "2026-11-21T01:02:00Z",
    status: "ready",
  };
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

describe("AccountPublicResearch", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("hides the previous account research while the next account loads", async () => {
    const companyB = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes("company-a")
          ? Promise.resolve(jsonResponse(research("company-a", "target-a")))
          : companyB.promise,
      ),
    );

    const view = render(<AccountPublicResearch companyId="company-a" />);
    expect(
      await screen.findByRole("link", { name: "View research" }),
    ).toHaveAttribute("href", "/find/target-a");

    view.rerender(<AccountPublicResearch companyId="company-b" />);
    expect(
      screen.queryByRole("link", { name: "View research" }),
    ).not.toBeInTheDocument();

    await act(async () => {
      companyB.resolve(jsonResponse(research("company-b", "target-b")));
      await companyB.promise;
    });
    expect(
      await screen.findByRole("link", { name: "View research" }),
    ).toHaveAttribute("href", "/find/target-b");
  });

  it("ignores a late response from the previous account", async () => {
    const companyA = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes("company-a")
          ? companyA.promise
          : Promise.resolve(jsonResponse(research("company-b", "target-b"))),
      ),
    );

    const view = render(<AccountPublicResearch companyId="company-a" />);
    view.rerender(<AccountPublicResearch companyId="company-b" />);
    expect(
      await screen.findByRole("link", { name: "View research" }),
    ).toHaveAttribute("href", "/find/target-b");

    await act(async () => {
      companyA.resolve(jsonResponse(research("company-a", "target-a")));
      await companyA.promise;
    });
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: "View research" }),
      ).toHaveAttribute("href", "/find/target-b"),
    );
    expect(screen.queryByRole("link")).not.toHaveAttribute(
      "href",
      "/find/target-a",
    );
  });

  it("ignores a late unavailable response from the previous account", async () => {
    const companyA = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes("company-a")
          ? companyA.promise
          : Promise.resolve(jsonResponse(research("company-b", "target-b"))),
      ),
    );

    const view = render(<AccountPublicResearch companyId="company-a" />);
    view.rerender(<AccountPublicResearch companyId="company-b" />);
    expect(
      await screen.findByRole("link", { name: "View research" }),
    ).toHaveAttribute("href", "/find/target-b");

    await act(async () => {
      companyA.resolve(
        jsonResponse(
          { code: "prospect_research_not_found", message: "Not found." },
          404,
        ),
      );
      await companyA.promise;
    });
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: "View research" }),
      ).toHaveAttribute("href", "/find/target-b"),
    );
  });

  it("does not carry an unavailable result into the next account", async () => {
    const companyA = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes("company-a")
          ? companyA.promise
          : Promise.resolve(jsonResponse(research("company-b", "target-b"))),
      ),
    );

    const view = render(<AccountPublicResearch companyId="company-a" />);
    await act(async () => {
      companyA.resolve(
        jsonResponse(
          { code: "prospect_research_not_found", message: "Not found." },
          404,
        ),
      );
      await companyA.promise;
    });
    expect(
      screen.queryByRole("link", { name: "View research" }),
    ).not.toBeInTheDocument();

    view.rerender(<AccountPublicResearch companyId="company-b" />);
    expect(
      await screen.findByRole("link", { name: "View research" }),
    ).toHaveAttribute("href", "/find/target-b");
  });

  it.each([
    ["another account", "company-b"],
    ["no account", null],
  ])("fails closed when research identifies %s", async (_label, companyId) => {
    const result = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => result.promise),
    );

    render(<AccountPublicResearch companyId="company-a" />);
    await act(async () => {
      result.resolve(
        jsonResponse({
          ...research("company-a", "foreign-target"),
          companyId,
        }),
      );
      await result.promise;
    });

    expect(
      screen.queryByRole("link", { name: "View research" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("foreign-target")).not.toBeInTheDocument();
  });

  it("fails closed when research identifies another organisation", async () => {
    const result = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => result.promise),
    );

    render(<AccountPublicResearch companyId="company-a" />);

    await act(async () => {
      result.resolve(
        jsonResponse({
          ...research("company-a", "foreign-target"),
          organisationId: "organisation-2",
        }),
      );
      await result.promise;
    });
    expect(
      screen.queryByRole("link", { name: "View research" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("foreign-target")).not.toBeInTheDocument();
  });

  it("keeps an untrusted research target inside the Find route", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(research("company-a", "../companies/other")),
        ),
      ),
    );

    render(<AccountPublicResearch companyId="company-a" />);

    expect(
      await screen.findByRole("link", { name: "View research" }),
    ).toHaveAttribute("href", "/find/..%2Fcompanies%2Fother");
  });
});
