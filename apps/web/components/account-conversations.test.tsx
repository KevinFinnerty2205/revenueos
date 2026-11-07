import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AccountConversations } from "@/components/account-conversations";

vi.mock("@/components/account-conversation-panel", () => ({
  AccountConversationPanel: () => <p>Account conversation history</p>,
}));
afterEach(() => vi.unstubAllGlobals());

it("opens account history without CRM, pipeline or ownership controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ id: "company-1", name: "Northstar", website: null }),
          { status: 200 },
        ),
      ),
    ),
  );
  render(<AccountConversations companyId="company-1" />);
  expect(
    await screen.findByRole("heading", { name: "Northstar" }),
  ).toBeVisible();
  expect(screen.getByText("Account conversation history")).toBeVisible();
  expect(
    screen.queryByText(/CRM details|Opportunity|Pipeline|Owner|custom fields/i),
  ).not.toBeInTheDocument();
  expect(
    screen
      .getAllByRole("link")
      .every((link) => link.getAttribute("href")?.startsWith("/conversations")),
  ).toBe(true);
});
