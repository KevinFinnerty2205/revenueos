import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BusinessEntityForm } from "@/components/business-entity-form";

const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("BusinessEntityForm", () => {
  afterEach(() => {
    router.push.mockReset();
    vi.unstubAllGlobals();
  });

  it("creates a validated company and returns to the list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValue(jsonResponse({ id: "company-1" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="companies" />);
    expect(
      await screen.findByRole("heading", { name: "Create account" }),
    ).toBeVisible();

    const name = screen.getByLabelText(/account name/i);
    expect(name).toBeRequired();
    fireEvent.change(name, { target: { value: "Acme Australia" } });
    fireEvent.change(screen.getByLabelText("Website"), {
      target: { value: "https://acme.example" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1]?.[0]).toContain("/api/v1/companies");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "POST" });
    expect(
      JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)),
    ).toMatchObject({
      name: "Acme Australia",
      website: "https://acme.example",
      status: "prospect",
    });
    expect(router.push).toHaveBeenCalledWith("/companies");
  });

  it("loads an existing opportunity into the edit form", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          items: [
            {
              id: "company-1",
              name: "Acme Australia",
            },
          ],
          page: 1,
          pageSize: 100,
          total: 1,
          pages: 1,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse([
          { userId: "user-1", displayName: "Alex Morgan", active: true },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          id: "opportunity-1",
          companyId: "company-1",
          name: "Expansion",
          stage: "proposal",
          status: "open",
          estimatedValue: "50000.00",
          currency: "AUD",
          expectedCloseDate: "2026-10-01",
          description: "Commercial expansion",
          updatedAt: "2026-07-24T10:00:00Z",
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ fieldAuthority: {} }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BusinessEntityForm entity="opportunities" entityId="opportunity-1" />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading form");
    expect(await screen.findByDisplayValue("Expansion")).toBeVisible();
    expect(screen.getByLabelText(/account/i)).toHaveValue("company-1");
    expect(screen.getByLabelText(/account/i)).not.toBeRequired();
    expect(screen.getByLabelText(/estimated value/i)).toHaveValue(50000);
    expect(screen.getByLabelText("Expected close date")).toHaveValue(
      "2026-10-01",
    );
    expect(screen.queryByLabelText(/probability/i)).not.toBeInTheDocument();
  });

  it("shows safe API validation errors without navigating", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse([]))
        .mockResolvedValue(
          jsonResponse(
            {
              code: "invalid_request",
              message: "The request could not be validated.",
              requestId: "request-1",
            },
            422,
          ),
        ),
    );

    render(<BusinessEntityForm entity="companies" />);
    fireEvent.change(await screen.findByLabelText(/account name/i), {
      target: { value: "Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The request could not be validated.",
    );
    expect(router.push).not.toHaveBeenCalled();
  });

  it("saves an explicitly promoted Contact whose business email is unknown", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/companies?pageSize=100"))
        return Promise.resolve(
          jsonResponse({
            items: [{ id: "company-1", name: "Acme Australia" }],
            page: 1,
            pageSize: 100,
            total: 1,
            pages: 1,
          }),
        );
      if (url.includes("/api/v1/crm/members"))
        return Promise.resolve(jsonResponse([]));
      if (init?.method === "PATCH")
        return Promise.resolve(jsonResponse({ id: "contact-1" }));
      if (url.includes("/api/v1/crm/records/contact/contact-1"))
        return Promise.resolve(jsonResponse({ fieldAuthority: {} }));
      return Promise.resolve(
        jsonResponse({
          id: "contact-1",
          companyId: "company-1",
          firstName: "Jordan",
          lastName: "Lee",
          email: null,
          phone: null,
          jobTitle: "Technology Director",
          linkedinUrl: null,
          status: "active",
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="contacts" entityId="contact-1" />);
    const email = await screen.findByLabelText("Business email");
    expect(email).not.toBeRequired();
    expect(email).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Job title"), {
      target: { value: "Chief Technology Officer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save contact" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.find((call) => call[1]?.method === "PATCH"),
      ).toBeDefined(),
    );
    const patchCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "PATCH",
    );
    expect(JSON.parse(String(patchCall?.[1]?.body))).toMatchObject({
      email: null,
      jobTitle: "Chief Technology Officer",
    });
  });

  it("preserves a provider-supplied business email when editing a promoted Contact", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/companies?pageSize=100"))
        return Promise.resolve(
          jsonResponse({
            items: [{ id: "company-1", name: "Northstar Facilities" }],
            page: 1,
            pageSize: 100,
            total: 1,
            pages: 1,
          }),
        );
      if (url.includes("/api/v1/crm/members"))
        return Promise.resolve(jsonResponse([]));
      if (url.includes("/api/v1/crm/records/contact/contact-1"))
        return Promise.resolve(jsonResponse({ fieldAuthority: {} }));
      return Promise.resolve(
        jsonResponse({
          id: "contact-1",
          companyId: "company-1",
          firstName: "Jane",
          lastName: "Smith",
          email: "jane.smith@northstar-facilities.example",
          status: "active",
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="contacts" entityId="contact-1" />);

    expect(await screen.findByLabelText("Business email")).toHaveValue(
      "jane.smith@northstar-facilities.example",
    );
  });

  it("renders external-CRM authoritative fields as read-only and omits them from updates", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/companies?pageSize=100"))
        return Promise.resolve(
          jsonResponse({
            items: [{ id: "company-1", name: "Acme Australia" }],
            page: 1,
            pageSize: 100,
            total: 1,
            pages: 1,
          }),
        );
      if (url.includes("/api/v1/crm/members"))
        return Promise.resolve(jsonResponse([]));
      if (url.includes("/api/v1/crm/records/contact/contact-1"))
        return Promise.resolve(
          jsonResponse({ fieldAuthority: { first_name: "crm_authoritative" } }),
        );
      if (init?.method === "PATCH")
        return Promise.resolve(jsonResponse({ id: "contact-1" }));
      return Promise.resolve(
        jsonResponse({
          id: "contact-1",
          companyId: "company-1",
          firstName: "Jordan",
          lastName: "Lee",
          email: "jordan@example.test",
          status: "active",
          updatedAt: "2026-08-29T10:00:00Z",
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="contacts" entityId="contact-1" />);
    expect(await screen.findByLabelText(/First name/)).toBeDisabled();
    expect(
      screen.getByText("CRM controlled · read-only in RevenueOS"),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Save contact" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => call[1]?.method === "PATCH"),
      ).toBe(true),
    );
    const patchCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "PATCH",
    );
    expect(JSON.parse(String(patchCall?.[1]?.body))).not.toHaveProperty(
      "firstName",
    );
  });
});
