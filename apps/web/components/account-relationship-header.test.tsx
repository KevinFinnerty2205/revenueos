import type { Company, Contact, EntityPage } from "@revenueos/shared";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountRelationshipHeader } from "@/components/account-relationship-header";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const company: Company = {
  id: "company/one",
  organisationId: "organisation-1",
  name: "Northstar Facilities",
  website: "https://www.northstar.example.test/about",
  industry: "Facilities",
  location: "Sydney",
  employeeCount: 120,
  status: "prospect",
  ownerUserId: "user-1",
  archivedAt: null,
  createdAt: "2026-11-01T00:00:00Z",
  updatedAt: "2026-11-01T00:00:00Z",
};

const participants: Contact[] = [
  {
    id: "contact-1",
    organisationId: "organisation-1",
    companyId: company.id,
    firstName: "Jordan",
    lastName: "Lee",
    email: "jordan@example.test",
    phone: null,
    jobTitle: "Operations Director",
    linkedinUrl: null,
    status: "active",
    ownerUserId: "user-1",
    archivedAt: null,
    createdAt: "2026-11-01T00:00:00Z",
    updatedAt: "2026-11-01T00:00:00Z",
  },
];

function contactPage(items: Contact[]): EntityPage<Contact> {
  return {
    items,
    page: 1,
    pageSize: 100,
    total: items.length,
    pages: items.length ? 1 : 0,
  };
}

describe("AccountRelationshipHeader", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("presents account context and participants without CRM administration", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        jsonResponse(
          String(input).includes("/contacts")
            ? contactPage(participants)
            : company,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountRelationshipHeader companyId="company/one" />);

    expect(
      screen.getByLabelText("Loading account relationship"),
    ).toHaveAttribute("aria-busy", "true");
    expect(
      await screen.findByRole("heading", { name: "Northstar Facilities" }),
    ).toBeVisible();
    expect(
      screen.getByText("Facilities · Sydney · northstar.example.test"),
    ).toBeVisible();
    expect(screen.getByText("Jordan Lee")).toBeVisible();
    expect(screen.getByText("Operations Director")).toBeVisible();
    expect(screen.getByText("1 person")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "← All conversations" }),
    ).toHaveAttribute("href", "/conversations");
    expect(screen.queryByText(/CRM details/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/opportunit/i)).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/v1/companies/company%2Fone"),
      ),
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("companyId=company%2Fone"),
      ),
    ).toBe(true);
  });

  it("shows a calm empty state when no participants are linked", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          jsonResponse(
            String(input).includes("/contacts") ? contactPage([]) : company,
          ),
        ),
      ),
    );

    render(<AccountRelationshipHeader companyId="company-1" />);

    expect(
      await screen.findByText(
        "Participants linked to future conversations will appear here.",
      ),
    ).toBeVisible();
    expect(screen.getByText("0 people")).toBeVisible();
  });

  it("fails safely and can retry the same account", async () => {
    let shouldFail = true;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (shouldFail) {
        return Promise.resolve(jsonResponse({}, 503));
      }
      return Promise.resolve(
        jsonResponse(
          String(input).includes("/contacts") ? contactPage([]) : company,
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountRelationshipHeader companyId="company-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Oryntela couldn’t load this account.",
    );
    shouldFail = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Northstar Facilities" }),
      ).toBeVisible(),
    );
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/v1/companies/company-1"),
      ),
    ).toBe(true);
  });
});
