import { render, screen } from "@testing-library/react";
import { usePathname } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConditionalClerkProvider } from "@/components/conditional-clerk-provider";

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }));
vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: Readonly<{ children: React.ReactNode }>) => (
    <div data-testid="clerk-provider">{children}</div>
  ),
}));

const mockedUsePathname = vi.mocked(usePathname);

describe("ConditionalClerkProvider", () => {
  beforeEach(() => mockedUsePathname.mockReturnValue("/opportunities"));

  it("keeps the public Deal Room outside the third-party identity provider", () => {
    mockedUsePathname.mockReturnValue("/deal-room");
    render(
      <ConditionalClerkProvider enabled>
        <p>Buyer room</p>
      </ConditionalClerkProvider>,
    );

    expect(screen.getByText("Buyer room")).toBeVisible();
    expect(screen.queryByTestId("clerk-provider")).toBeNull();
  });

  it.each([
    "/",
    "/platform",
    "/pricing",
    "/integrations",
    "/security",
    "/contact",
    "/privacy",
    "/terms",
  ])(
    "keeps marketing route %s independent of the identity provider",
    (pathname) => {
      mockedUsePathname.mockReturnValue(pathname);
      render(
        <ConditionalClerkProvider enabled>
          <p>Public website</p>
        </ConditionalClerkProvider>,
      );

      expect(screen.getByText("Public website")).toBeVisible();
      expect(screen.queryByTestId("clerk-provider")).toBeNull();
    },
  );

  it.each([
    "/opportunities/opportunity-1",
    "/settings/integrations/google",
    "/create/presentations/presentation-1",
    "/billing/success",
  ])("retains the identity provider for authenticated path %s", (pathname) => {
    mockedUsePathname.mockReturnValue(pathname);
    render(
      <ConditionalClerkProvider enabled>
        <p>Seller app</p>
      </ConditionalClerkProvider>,
    );

    expect(screen.getByTestId("clerk-provider")).toBeVisible();
  });

  it("keeps the branded 404 independent of the identity provider", () => {
    mockedUsePathname.mockReturnValue("/this-page-does-not-exist");
    render(
      <ConditionalClerkProvider enabled>
        <p>Page not found</p>
      </ConditionalClerkProvider>,
    );

    expect(screen.getByText("Page not found")).toBeVisible();
    expect(screen.queryByTestId("clerk-provider")).toBeNull();
  });
});
