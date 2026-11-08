import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CompanyAccountPage from "@/app/(protected)/companies/[id]/page";

vi.mock("@/components/account-relationship-header", () => ({
  AccountRelationshipHeader: ({ companyId }: { companyId: string }) => (
    <h1>Relationship {companyId}</h1>
  ),
}));

vi.mock("@/components/account-conversation-panel", () => ({
  AccountConversationPanel: ({ companyId }: { companyId: string }) => (
    <section aria-label="Conversation memory">
      Conversations {companyId}
    </section>
  ),
}));

vi.mock("@/components/account-public-research", () => ({
  AccountPublicResearch: ({ companyId }: { companyId: string }) => (
    <section aria-label="Public research">Research {companyId}</section>
  ),
}));

describe("CompanyAccountPage", () => {
  it("keeps the primary account journey focused on relationship memory", async () => {
    render(
      await CompanyAccountPage({
        params: Promise.resolve({ id: "company-1" }),
      }),
    );

    expect(
      screen.getByRole("heading", { name: "Relationship company-1" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Conversation memory")).toBeVisible();
    expect(screen.getByLabelText("Public research")).toBeVisible();
    expect(screen.queryByText(/CRM details/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Create opportunity/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Business Case/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Plan presentation/i)).not.toBeInTheDocument();
  });
});
