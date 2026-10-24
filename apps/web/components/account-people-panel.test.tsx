import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Contact, EntityPage } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountPeoplePanel } from "@/components/account-people-panel";
import { apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
const mockedApiRequest = vi.mocked(apiRequest);

const person: Contact = {
  id: "contact-1",
  organisationId: "organisation-1",
  companyId: "company/one",
  firstName: "[DEMO] Jordan",
  lastName: "Lee",
  email: "jordan.lee@example.test",
  phone: null,
  jobTitle: "Finance approver",
  linkedinUrl: null,
  status: "active",
  ownerUserId: "user-1",
  archivedAt: null,
  createdAt: "2026-10-24T00:00:00Z",
  updatedAt: "2026-10-24T00:00:00Z",
};

function page(items: Contact[]): EntityPage<Contact> {
  return {
    items,
    page: 1,
    pageSize: 100,
    total: items.length,
    pages: items.length ? 1 : 0,
  };
}

afterEach(() => {
  mockedApiRequest.mockReset();
});

describe("AccountPeoplePanel", () => {
  it("loads and links the people scoped to the exact account", async () => {
    mockedApiRequest.mockResolvedValueOnce(page([person]));

    render(<AccountPeoplePanel companyId="company/one" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading linked people",
    );
    expect(
      await screen.findByRole("link", { name: "[DEMO] Jordan Lee" }),
    ).toHaveAttribute("href", "/contacts/contact-1");
    expect(screen.getByText(/Finance approver/)).toHaveTextContent(
      "jordan.lee@example.test",
    );
    expect(screen.getByRole("link", { name: "Add person" })).toHaveAttribute(
      "href",
      "/contacts/new?companyId=company%2Fone",
    );
    expect(mockedApiRequest).toHaveBeenCalledWith(
      "/api/v1/contacts?companyId=company%2Fone&page=1&pageSize=100&sortBy=last_name&sortOrder=asc",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows an honest empty state", async () => {
    mockedApiRequest.mockResolvedValueOnce(page([]));

    render(<AccountPeoplePanel companyId="company-1" />);

    expect(
      await screen.findByText("No people are linked to this account yet."),
    ).toBeVisible();
  });

  it("offers a bounded retry after a load failure", async () => {
    mockedApiRequest
      .mockRejectedValueOnce(new Error("People are temporarily unavailable."))
      .mockResolvedValueOnce(page([person]));

    render(<AccountPeoplePanel companyId="company-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "People are temporarily unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(mockedApiRequest).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByRole("link", { name: "[DEMO] Jordan Lee" }),
    ).toBeVisible();
  });
});
