import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InteractionForm } from "@/components/interaction-form";

const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyPage = {
  items: [],
  page: 1,
  pageSize: 100,
  total: 0,
  pages: 0,
};

describe("InteractionForm", () => {
  afterEach(() => {
    router.push.mockReset();
    vi.unstubAllGlobals();
  });

  it("creates a deliberately supplied interaction and follows its stable URL", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: "interaction-1" }, 201));
      }
      if (String(input).includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [{ id: "company-1", name: "Acme Australia" }],
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          ...emptyPage,
          items: [{ id: "opportunity-1", name: "Expansion" }],
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading interaction options",
    );
    await screen.findByRole("heading", { name: "Create interaction" });
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Executive planning lunch" },
    });
    fireEvent.change(screen.getByLabelText("Interaction type"), {
      target: { value: "executive_lunch" },
    });
    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "company-1" },
    });
    fireEvent.change(screen.getByLabelText("Opportunity"), {
      target: { value: "opportunity-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create interaction" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/interactions/interaction-1"),
    );
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/api/v1/interactions") &&
        init?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      title: "Executive planning lunch",
      interactionType: "executive_lunch",
      lifecycleStatus: "planned",
      companyId: "company-1",
      opportunityId: "opportunity-1",
    });
  });

  it("shows a safe options-loading error without exposing a partial form", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              code: "persistence_unavailable",
              message: "Interaction options are temporarily unavailable.",
              requestId: "request-2",
            },
            503,
          ),
        ),
      ),
    );

    render(<InteractionForm />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Interaction options are temporarily unavailable.",
    );
    expect(
      screen.queryByRole("button", { name: "Create interaction" }),
    ).not.toBeInTheDocument();
  });

  it("creates a phone call with an explicit direction and selected contact", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: "phone-call-1" }, 201));
      }
      if (path.includes("/contacts")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [
              {
                id: "contact-1",
                companyId: "company-1",
                firstName: "Jordan",
                lastName: "Lee",
                jobTitle: "Commercial Director",
              },
            ],
          }),
        );
      }
      if (path.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [{ id: "company-1", name: "Acme Australia" }],
          }),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);
    await screen.findByRole("heading", { name: "Create interaction" });
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Commercial check-in" },
    });
    fireEvent.change(screen.getByLabelText("Interaction type"), {
      target: { value: "phone_call" },
    });
    expect(screen.getByText(/does not intercept or record/i)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "company-1" },
    });
    fireEvent.change(screen.getByLabelText("Call direction"), {
      target: { value: "outbound" },
    });
    fireEvent.change(screen.getByLabelText("Contact"), {
      target: { value: "contact-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create interaction" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/interactions/phone-call-1"),
    );
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/api/v1/interactions") &&
        init?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      interactionType: "phone_call",
      companyId: "company-1",
      contactId: "contact-1",
      callDirection: "outbound",
    });
  });

  it("preserves safe relationship context from an in-app create link", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/contacts")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [
              {
                id: "contact-1",
                companyId: "company-1",
                firstName: "Jordan",
                lastName: "Lee",
              },
            ],
          }),
        );
      }
      if (path.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [{ id: "company-1", name: "Acme Australia" }],
          }),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <InteractionForm
        initialContactId="contact-1"
        initialInteractionType="phone_call"
      />,
    );

    expect(await screen.findByLabelText("Contact")).toHaveValue("contact-1");
    expect(screen.getByLabelText("Company")).toHaveValue("company-1");
    expect(screen.getByLabelText("Interaction type")).toHaveValue("phone_call");
  });

  it("loads an exact linked contact and its account beyond the first page", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/api/v1/contacts/contact-101")) {
        return Promise.resolve(
          jsonResponse({
            id: "contact-101",
            companyId: "company-101",
            firstName: "Taylor",
            lastName: "Ng",
          }),
        );
      }
      if (path.endsWith("/api/v1/companies/company-101")) {
        return Promise.resolve(
          jsonResponse({ id: "company-101", name: "Beyond Page Account" }),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <InteractionForm
        initialContactId="contact-101"
        initialInteractionType="phone_call"
      />,
    );

    expect(await screen.findByLabelText("Contact")).toHaveValue("contact-101");
    expect(screen.getByRole("option", { name: "Taylor Ng" })).toBeVisible();
    expect(screen.getByLabelText("Company")).toHaveValue("company-101");
    expect(
      screen.getByRole("option", { name: "Beyond Page Account" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/contacts/contact-101"),
      expect.any(Object),
    );
  });

  it("syncs changed linked props until relationship context becomes dirty", async () => {
    const companies = ["1", "2", "3"].map((suffix) => ({
      id: `company-${suffix}`,
      name: `Account ${suffix}`,
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          jsonResponse(
            String(input).includes("/companies")
              ? { ...emptyPage, items: companies }
              : emptyPage,
          ),
        ),
      ),
    );

    const { rerender } = render(
      <InteractionForm initialCompanyId="company-1" />,
    );
    expect(await screen.findByLabelText("Company")).toHaveValue("company-1");
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Keep this draft title" },
    });

    rerender(
      <InteractionForm
        initialCompanyId="company-2"
        initialInteractionType="online_meeting"
      />,
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Company")).toHaveValue("company-2"),
    );
    expect(screen.getByLabelText("Interaction type")).toHaveValue(
      "online_meeting",
    );
    expect(screen.getByLabelText("Title")).toHaveValue("Keep this draft title");

    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "company-1" },
    });
    rerender(
      <InteractionForm
        initialCompanyId="company-3"
        initialInteractionType="phone_call"
      />,
    );

    expect(
      await screen.findByText(/current selections were kept/i),
    ).toBeVisible();
    expect(screen.getByLabelText("Company")).toHaveValue("company-1");
    expect(screen.getByLabelText("Interaction type")).toHaveValue(
      "online_meeting",
    );
    fireEvent.click(screen.getByRole("button", { name: "Use linked context" }));
    expect(screen.getByLabelText("Company")).toHaveValue("company-3");
    expect(screen.getByLabelText("Interaction type")).toHaveValue("phone_call");
  });
});
