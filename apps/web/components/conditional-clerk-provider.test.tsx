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

  it("retains the identity provider for the authenticated application", () => {
    render(
      <ConditionalClerkProvider enabled>
        <p>Seller app</p>
      </ConditionalClerkProvider>,
    );

    expect(screen.getByTestId("clerk-provider")).toBeVisible();
  });
});
