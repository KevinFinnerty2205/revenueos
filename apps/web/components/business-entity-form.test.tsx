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
      .mockResolvedValue(jsonResponse({ id: "company-1" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="companies" />);
    expect(
      await screen.findByRole("heading", { name: "Create company" }),
    ).toBeVisible();

    const name = screen.getByLabelText(/company name/i);
    expect(name).toBeRequired();
    fireEvent.change(name, { target: { value: "Acme Australia" } });
    fireEvent.change(screen.getByLabelText("Website"), {
      target: { value: "https://acme.example" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create company" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/v1/companies");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "POST" });
    expect(
      JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body)),
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
        jsonResponse({
          id: "opportunity-1",
          companyId: "company-1",
          name: "Expansion",
          stage: "proposal",
          value: "50000.00",
          currency: "AUD",
          probability: 70,
          expectedCloseDate: "2026-10-01",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BusinessEntityForm entity="opportunities" entityId="opportunity-1" />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading form");
    expect(await screen.findByDisplayValue("Expansion")).toBeVisible();
    expect(screen.getByLabelText(/company/i)).toHaveValue("company-1");
    expect(screen.getByLabelText(/probability/i)).toHaveValue(70);
  });

  it("shows safe API validation errors without navigating", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
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
    fireEvent.change(await screen.findByLabelText(/company name/i), {
      target: { value: "Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create company" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The request could not be validated.",
    );
    expect(router.push).not.toHaveBeenCalled();
  });
});
