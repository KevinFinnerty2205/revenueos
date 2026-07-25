import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SignOutPage from "@/app/sign-out/page";

describe("sign-out page", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("fails closed without rendering Clerk controls when Clerk is incomplete", () => {
    vi.stubEnv("AUTH_MODE", "clerk");
    vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "");

    render(<SignOutPage />);

    expect(screen.getByRole("heading", { name: "Sign out" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Return to RevenueOS" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Sign out securely" }),
    ).not.toBeInTheDocument();
  });
});
