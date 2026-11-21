import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { Company, Contact, Opportunity } from "@revenueos/shared";
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

const exactRelationshipCases = (
  ["company", "contact", "opportunity"] as const
).flatMap((entity) =>
  (["valid", "wrong_id", "archived", "missing"] as const).map((outcome) => ({
    entity,
    outcome,
  })),
);

function companyFixture(overrides: Partial<Company> = {}): Company {
  return {
    id: "company-1",
    organisationId: "organisation-1",
    name: "Acme Australia",
    website: null,
    industry: null,
    location: null,
    employeeCount: null,
    status: "active",
    ownerUserId: "user-1",
    archivedAt: null,
    createdAt: "2026-11-20T00:00:00Z",
    updatedAt: "2026-11-20T00:00:00Z",
    ...overrides,
  };
}

function contactFixture(overrides: Partial<Contact> = {}): Contact {
  return {
    id: "contact-1",
    organisationId: "organisation-1",
    companyId: "company-1",
    firstName: "Jordan",
    lastName: "Lee",
    email: null,
    phone: null,
    jobTitle: null,
    linkedinUrl: null,
    status: "active",
    ownerUserId: "user-1",
    archivedAt: null,
    createdAt: "2026-11-20T00:00:00Z",
    updatedAt: "2026-11-20T00:00:00Z",
    ...overrides,
  };
}

function opportunityFixture(overrides: Partial<Opportunity> = {}): Opportunity {
  return {
    id: "opportunity-1",
    organisationId: "organisation-1",
    companyId: "company-1",
    name: "Expansion",
    stage: "discovery",
    status: "open",
    estimatedValue: null,
    currency: null,
    expectedCloseDate: null,
    ownerUserId: "user-1",
    description: null,
    archivedAt: null,
    createdAt: "2026-11-20T00:00:00Z",
    updatedAt: "2026-11-20T00:00:00Z",
    ...overrides,
  };
}

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
            items: [companyFixture()],
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          ...emptyPage,
          items: [opportunityFixture()],
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading optional relationship context",
    );
    await screen.findByRole("heading", { name: "Add conversation" });
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Executive planning lunch" },
    });
    fireEvent.change(screen.getByLabelText("Conversation type"), {
      target: { value: "executive_lunch" },
    });
    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "company-1" },
    });
    fireEvent.change(screen.getByLabelText("Opportunity"), {
      target: { value: "opportunity-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/conversations/interaction-1"),
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

  it("preserves an explicitly linked opportunity without loading CRM opportunity administration", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/api/v1/opportunities/old-opportunity")) {
        return Promise.resolve(
          jsonResponse(
            opportunityFixture({
              id: "old-opportunity",
              companyId: "old-company",
              name: "Existing opportunity",
            }),
          ),
        );
      }
      if (path.endsWith("/api/v1/companies/old-company")) {
        return Promise.resolve(
          jsonResponse(
            companyFixture({ id: "old-company", name: "Existing account" }),
          ),
        );
      }
      return Promise.resolve(
        jsonResponse(
          init?.method === "POST" ? { id: "conversation-1" } : emptyPage,
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <InteractionForm
        conversationOnly
        initialOpportunityId="old-opportunity"
      />,
    );

    await screen.findByRole("heading", { name: "Add conversation" });
    await waitFor(() =>
      expect(
        screen.queryByText(/loading optional relationship context/i),
      ).not.toBeInTheDocument(),
    );
    expect(screen.queryByLabelText("Opportunity")).not.toBeInTheDocument();
    expect(screen.getByText("Add a scheduled time (optional)")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Discovery" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/conversations/conversation-1"),
    );
    const posted = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(String(posted?.[1]?.body))).toMatchObject({
      title: "Discovery",
      companyId: "old-company",
      opportunityId: "old-opportunity",
    });
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/v1/opportunities?pageSize="),
      ),
    ).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/opportunities/old-opportunity"),
      expect.any(Object),
    );
  });

  it.each(exactRelationshipCases)(
    "adopts only a valid exact $entity record when it is $outcome",
    async ({ entity, outcome }) => {
      const requestedId = `linked-${entity}`;
      const plural =
        entity === "company"
          ? "companies"
          : entity === "opportunity"
            ? "opportunities"
            : "contacts";
      const fetchMock = vi.fn(
        (input: RequestInfo | URL, init?: RequestInit) => {
          const path = String(input);
          if (init?.method === "POST") {
            return Promise.resolve(
              jsonResponse({ id: `created-${entity}-${outcome}` }, 201),
            );
          }
          if (path.endsWith(`/api/v1/${plural}/${requestedId}`)) {
            if (outcome === "missing") {
              return Promise.resolve(jsonResponse({ code: "not_found" }, 404));
            }
            const id = outcome === "wrong_id" ? `wrong-${entity}` : requestedId;
            const archivedAt =
              outcome === "archived" ? "2026-11-21T00:00:00Z" : null;
            if (entity === "company") {
              return Promise.resolve(
                jsonResponse(companyFixture({ id, archivedAt })),
              );
            }
            if (entity === "contact") {
              return Promise.resolve(
                jsonResponse(
                  contactFixture({
                    id,
                    companyId: "contact-company",
                    archivedAt,
                  }),
                ),
              );
            }
            return Promise.resolve(
              jsonResponse(
                opportunityFixture({
                  id,
                  companyId: null,
                  archivedAt,
                }),
              ),
            );
          }
          if (
            entity === "contact" &&
            outcome === "valid" &&
            path.endsWith("/api/v1/companies/contact-company")
          ) {
            return Promise.resolve(
              jsonResponse(
                companyFixture({
                  id: "contact-company",
                  name: "Contact account",
                }),
              ),
            );
          }
          return Promise.resolve(jsonResponse(emptyPage));
        },
      );
      vi.stubGlobal("fetch", fetchMock);

      render(
        <InteractionForm
          conversationOnly={entity === "opportunity"}
          initialCompanyId={entity === "company" ? requestedId : ""}
          initialContactId={entity === "contact" ? requestedId : ""}
          initialOpportunityId={entity === "opportunity" ? requestedId : ""}
          initialInteractionType={
            entity === "contact" ? "phone_call" : "manual_interaction"
          }
        />,
      );

      if (outcome === "valid") {
        if (entity === "company") {
          await waitFor(() =>
            expect(screen.getByLabelText("Company")).toHaveValue(requestedId),
          );
        } else if (entity === "contact") {
          await waitFor(() =>
            expect(screen.getByLabelText("Person")).toHaveValue(requestedId),
          );
          expect(screen.getByLabelText("Company")).toHaveValue(
            "contact-company",
          );
        } else {
          await waitFor(() =>
            expect(
              screen.queryByText(/loading optional relationship context/i),
            ).not.toBeInTheDocument(),
          );
          expect(
            fetchMock.mock.calls.some(([input]) =>
              String(input).endsWith(
                "/api/v1/opportunities/linked-opportunity",
              ),
            ),
          ).toBe(true);
        }
      } else {
        expect(
          await screen.findByText(/could not be verified as active/i),
        ).toBeVisible();
      }

      fireEvent.change(screen.getByLabelText("Title"), {
        target: { value: `Exact ${entity} ${outcome}` },
      });
      fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));
      await waitFor(() =>
        expect(router.push).toHaveBeenCalledWith(
          `/conversations/created-${entity}-${outcome}`,
        ),
      );
      const createCall = fetchMock.mock.calls.find(
        ([input, init]) =>
          String(input).endsWith("/api/v1/interactions") &&
          init?.method === "POST",
      );
      const payload = JSON.parse(String(createCall?.[1]?.body)) as Record<
        string,
        unknown
      >;
      expect(payload[`${entity}Id`]).toBe(
        outcome === "valid" ? requestedId : null,
      );
      if (entity === "contact") {
        expect(payload.companyId).toBe(
          outcome === "valid" ? "contact-company" : null,
        );
      }
    },
  );

  it.each(["wrong_id", "archived", "missing"] as const)(
    "rejects a %s derived company for an exact linked person",
    async (outcome) => {
      const fetchMock = vi.fn(
        (input: RequestInfo | URL, init?: RequestInit) => {
          const path = String(input);
          if (init?.method === "POST") {
            return Promise.resolve(
              jsonResponse({ id: `derived-company-${outcome}` }, 201),
            );
          }
          if (path.endsWith("/api/v1/contacts/linked-contact")) {
            return Promise.resolve(
              jsonResponse(
                contactFixture({
                  id: "linked-contact",
                  companyId: "derived-company",
                }),
              ),
            );
          }
          if (path.endsWith("/api/v1/companies/derived-company")) {
            if (outcome === "missing") {
              return Promise.resolve(jsonResponse({ code: "not_found" }, 404));
            }
            return Promise.resolve(
              jsonResponse(
                companyFixture({
                  id:
                    outcome === "wrong_id"
                      ? "wrong-company"
                      : "derived-company",
                  archivedAt:
                    outcome === "archived" ? "2026-11-21T00:00:00Z" : null,
                }),
              ),
            );
          }
          return Promise.resolve(jsonResponse(emptyPage));
        },
      );
      vi.stubGlobal("fetch", fetchMock);

      render(
        <InteractionForm
          initialContactId="linked-contact"
          initialInteractionType="phone_call"
        />,
      );

      expect(
        await screen.findByText(
          /linked company could not be verified as active/i,
        ),
      ).toBeVisible();
      expect(screen.getByLabelText("Company")).toHaveValue("");
      expect(screen.getByLabelText("Person")).toHaveValue("");
      fireEvent.change(screen.getByLabelText("Title"), {
        target: { value: `Derived company ${outcome}` },
      });
      fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));
      await waitFor(() =>
        expect(router.push).toHaveBeenCalledWith(
          `/conversations/derived-company-${outcome}`,
        ),
      );
      const createCall = fetchMock.mock.calls.find(
        ([input, init]) =>
          String(input).endsWith("/api/v1/interactions") &&
          init?.method === "POST",
      );
      expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
        companyId: null,
        contactId: null,
      });
    },
  );

  it("drops linked people and opportunities that do not belong to the verified company", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: "compatible-context" }, 201));
      }
      if (path.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [
              companyFixture({ id: "company-a", name: "Company A" }),
              companyFixture({ id: "company-b", name: "Company B" }),
            ],
          }),
        );
      }
      if (path.includes("/opportunities")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [
              opportunityFixture({
                id: "opportunity-b",
                companyId: "company-b",
              }),
            ],
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          ...emptyPage,
          items: [contactFixture({ id: "contact-b", companyId: "company-b" })],
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <InteractionForm
        initialCompanyId="company-a"
        initialContactId="contact-b"
        initialOpportunityId="opportunity-b"
        initialInteractionType="phone_call"
      />,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("Company")).toHaveValue("company-a"),
    );
    expect(screen.getByLabelText("Opportunity")).toHaveValue("");
    expect(screen.getByLabelText("Person")).toHaveValue("");
    expect(
      screen.getByText(/linked opportunity could not be verified as active/i),
    ).toBeVisible();
    expect(
      screen.getByText(/linked person could not be verified as active/i),
    ).toBeVisible();

    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Compatible context only" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));
    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith(
        "/conversations/compatible-context",
      ),
    );
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/api/v1/interactions") &&
        init?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      companyId: "company-a",
      opportunityId: null,
      contactId: null,
    });
  });

  it("keeps unlinked conversation creation available when optional sources fail", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "POST"
          ? jsonResponse({ id: "unlinked-conversation" }, 201)
          : jsonResponse(
              {
                code: "persistence_unavailable",
                message: "Relationship source unavailable.",
                requestId: "request-2",
              },
              503,
            ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);
    expect(
      await screen.findByText(/company options are temporarily unavailable/i),
    ).toBeVisible();
    expect(screen.getByLabelText("Company")).toBeDisabled();
    expect(screen.getByLabelText("Opportunity")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Unlinked founder conversation" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith(
        "/conversations/unlinked-conversation",
      ),
    );
    const posted = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(String(posted?.[1]?.body))).toMatchObject({
      title: "Unlinked founder conversation",
      companyId: null,
      opportunityId: null,
      contactId: null,
    });
  });

  it("keeps phone-call creation available when people options fail", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: "unlinked-call" }, 201));
      }
      if (String(input).includes("/contacts")) {
        return Promise.resolve(jsonResponse({ code: "unavailable" }, 503));
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);
    await screen.findByRole("button", { name: "Add conversation" });
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Unlinked phone check-in" },
    });
    fireEvent.change(screen.getByLabelText("Conversation type"), {
      target: { value: "phone_call" },
    });
    expect(
      await screen.findByText(/people options are temporarily unavailable/i),
    ).toBeVisible();
    expect(screen.getByLabelText("Person")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/conversations/unlinked-call"),
    );
    const posted = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(String(posted?.[1]?.body))).toMatchObject({
      interactionType: "phone_call",
      contactId: null,
    });
  });

  it("exposes settled relationship sources while another optional source is pending", async () => {
    let resolveContacts: ((response: Response) => void) | undefined;
    const pendingContacts = new Promise<Response>((resolve) => {
      resolveContacts = resolve;
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/contacts")) return pendingContacts;
      if (path.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [
              companyFixture({ id: "company-ready", name: "Ready company" }),
            ],
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          ...emptyPage,
          items: [
            opportunityFixture({
              id: "opportunity-ready",
              companyId: null,
              name: "Ready opportunity",
            }),
          ],
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);

    expect(
      await screen.findByRole("option", { name: "Ready company" }),
    ).toBeVisible();
    expect(
      screen.getByRole("option", { name: "Ready opportunity" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Company")).toBeEnabled();
    expect(screen.getByLabelText("Opportunity")).toBeEnabled();
    expect(
      screen.getByText(/loading optional relationship context/i),
    ).toBeVisible();

    await act(async () => {
      resolveContacts?.(jsonResponse(emptyPage));
      await Promise.resolve();
    });
    await waitFor(() =>
      expect(
        screen.queryByText(/loading optional relationship context/i),
      ).toBeNull(),
    );
  });

  it("keeps page options usable when an exact linked company fails", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/api/v1/companies/missing-company")) {
        return Promise.resolve(jsonResponse({ code: "not_found" }, 404));
      }
      if (path.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [
              companyFixture({
                id: "company-available",
                name: "Available company",
              }),
            ],
          }),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm initialCompanyId="missing-company" />);

    expect(
      await screen.findByText(
        /linked company could not be verified as active/i,
      ),
    ).toBeVisible();
    expect(screen.getByLabelText("Company")).toBeEnabled();
    expect(screen.getByLabelText("Company")).toHaveValue("");
    expect(
      screen.getByRole("option", { name: "Available company" }),
    ).toBeVisible();
  });

  it("retries optional sources without discarding core edits", async () => {
    let companyLoads = 0;
    let resolveCompanyRetry: ((response: Response) => void) | undefined;
    const companyRetry = new Promise<Response>((resolve) => {
      resolveCompanyRetry = resolve;
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/companies")) {
        companyLoads += 1;
        return companyLoads === 1
          ? Promise.resolve(jsonResponse({ code: "unavailable" }, 503))
          : companyRetry;
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);
    await screen.findByText(/company options are temporarily unavailable/i);
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Keep this conversation title" },
    });
    const retryButton = screen.getByRole("button", {
      name: "Retry companies",
    });
    retryButton.focus();
    fireEvent.click(retryButton);

    const retryingButton = await screen.findByRole("button", {
      name: "Retrying…",
    });
    expect(retryingButton).toBeDisabled();
    expect(retryingButton).toHaveFocus();
    expect(
      screen.getByText(/company options are temporarily unavailable/i),
    ).toBeVisible();

    await act(async () => {
      resolveCompanyRetry?.(
        jsonResponse({
          ...emptyPage,
          items: [
            companyFixture({
              id: "company-restored",
              name: "Restored company",
            }),
          ],
        }),
      );
      await Promise.resolve();
    });

    expect(
      await screen.findByRole("option", { name: "Restored company" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Title")).toHaveValue(
      "Keep this conversation title",
    );
    expect(companyLoads).toBe(2);
  });

  it("retries only the failed source and preserves ready relationship selections", async () => {
    let contactLoads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: "selected-context" }, 201));
      }
      if (path.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [companyFixture({ name: "Selected company" })],
          }),
        );
      }
      if (path.includes("/opportunities")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [opportunityFixture({ name: "Selected opportunity" })],
          }),
        );
      }
      contactLoads += 1;
      return contactLoads === 1
        ? Promise.resolve(jsonResponse({ code: "unavailable" }, 503))
        : new Promise<Response>(() => undefined);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);
    await screen.findByRole("option", { name: "Selected company" });
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Keep selected context" },
    });
    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "company-1" },
    });
    fireEvent.change(screen.getByLabelText("Opportunity"), {
      target: { value: "opportunity-1" },
    });
    fireEvent.change(screen.getByLabelText("Conversation type"), {
      target: { value: "phone_call" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Retry people" }));
    await waitFor(() => expect(contactLoads).toBe(2));

    expect(screen.getByLabelText("Company")).toBeEnabled();
    expect(screen.getByLabelText("Company")).toHaveValue("company-1");
    expect(screen.getByLabelText("Opportunity")).toBeEnabled();
    expect(screen.getByLabelText("Opportunity")).toHaveValue("opportunity-1");
    fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith(
        "/conversations/selected-context",
      ),
    );
    const posted = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(String(posted?.[1]?.body))).toMatchObject({
      companyId: "company-1",
      opportunityId: "opportunity-1",
      contactId: null,
    });
  });

  it("ignores a deferred retry from an obsolete linked context", async () => {
    let companyLoads = 0;
    let resolveOldRetry: ((response: Response) => void) | undefined;
    const oldRetry = new Promise<Response>((resolve) => {
      resolveOldRetry = resolve;
    });
    let resolveNewLoad: ((response: Response) => void) | undefined;
    const newLoad = new Promise<Response>((resolve) => {
      resolveNewLoad = resolve;
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (!path.includes("/companies")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      companyLoads += 1;
      if (companyLoads === 1) {
        return Promise.resolve(jsonResponse({ code: "unavailable" }, 503));
      }
      if (companyLoads === 2) return oldRetry;
      return newLoad;
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <InteractionForm initialCompanyId="company-a" />,
    );
    await screen.findByText(/company options are temporarily unavailable/i);
    fireEvent.click(screen.getByRole("button", { name: "Retry companies" }));
    await waitFor(() => expect(companyLoads).toBe(2));

    await act(async () => {
      rerender(<InteractionForm initialCompanyId="company-b" />);
      resolveOldRetry?.(
        jsonResponse({
          ...emptyPage,
          items: [companyFixture({ id: "company-a", name: "Company A" })],
        }),
      );
      await Promise.resolve();
    });
    await waitFor(() => expect(companyLoads).toBe(3));
    expect(screen.queryByRole("option", { name: "Company A" })).toBeNull();
    expect(screen.getByLabelText("Company")).toBeDisabled();

    await act(async () => {
      resolveNewLoad?.(
        jsonResponse({
          ...emptyPage,
          items: [companyFixture({ id: "company-b", name: "Company B" })],
        }),
      );
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(screen.getByLabelText("Company")).toHaveValue("company-b"),
    );
    expect(screen.queryByRole("option", { name: "Company A" })).toBeNull();
    expect(screen.getByRole("option", { name: "Company B" })).toBeVisible();
    expect(screen.getByLabelText("Company")).toHaveValue("company-b");
  });

  it("ignores deferred base loads after a type-only linked-context change", async () => {
    const pendingLoads = Array.from({ length: 6 }, () => {
      let resolve: ((response: Response) => void) | undefined;
      const response = new Promise<Response>((settle) => {
        resolve = settle;
      });
      return { response, resolve: (value: Response) => resolve?.(value) };
    });
    const fetchMock = vi.fn(() => {
      const pendingLoad = pendingLoads[fetchMock.mock.calls.length - 1];
      if (!pendingLoad) throw new Error("Unexpected option request");
      return pendingLoad.response;
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <InteractionForm initialInteractionType="online_meeting" />,
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    await act(async () => {
      rerender(<InteractionForm initialInteractionType="phone_call" />);
      for (const pendingLoad of pendingLoads.slice(0, 3)) {
        pendingLoad.resolve(jsonResponse(emptyPage));
      }
      await Promise.resolve();
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));

    await act(async () => {
      for (const pendingLoad of pendingLoads.slice(3)) {
        pendingLoad.resolve(jsonResponse(emptyPage));
      }
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(screen.getByLabelText("Conversation type")).toHaveValue(
        "phone_call",
      ),
    );
    expect(screen.getByLabelText("Conversation type")).not.toHaveValue(
      "online_meeting",
    );
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
            items: [contactFixture({ jobTitle: "Commercial Director" })],
          }),
        );
      }
      if (path.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [companyFixture()],
          }),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionForm />);
    await screen.findByRole("heading", { name: "Add conversation" });
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Commercial check-in" },
    });
    fireEvent.change(screen.getByLabelText("Conversation type"), {
      target: { value: "phone_call" },
    });
    expect(screen.getByText(/does not intercept or record/i)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "company-1" },
    });
    fireEvent.change(screen.getByLabelText("Call direction"), {
      target: { value: "outbound" },
    });
    fireEvent.change(screen.getByLabelText("Person"), {
      target: { value: "contact-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add conversation" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/conversations/phone-call-1"),
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
            items: [contactFixture()],
          }),
        );
      }
      if (path.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [companyFixture()],
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

    expect(await screen.findByLabelText("Person")).toHaveValue("contact-1");
    expect(screen.getByLabelText("Company")).toHaveValue("company-1");
    expect(screen.getByLabelText("Conversation type")).toHaveValue(
      "phone_call",
    );
  });

  it("loads an exact linked contact and its account beyond the first page", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/api/v1/contacts/contact-101")) {
        return Promise.resolve(
          jsonResponse(
            contactFixture({
              id: "contact-101",
              companyId: "company-101",
              firstName: "Taylor",
              lastName: "Ng",
            }),
          ),
        );
      }
      if (path.endsWith("/api/v1/companies/company-101")) {
        return Promise.resolve(
          jsonResponse(
            companyFixture({
              id: "company-101",
              name: "Beyond Page Account",
            }),
          ),
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

    expect(await screen.findByLabelText("Person")).toHaveValue("contact-101");
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
    const companies = ["1", "2", "3"].map((suffix) =>
      companyFixture({
        id: `company-${suffix}`,
        name: `Account ${suffix}`,
      }),
    );
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
    expect(screen.getByLabelText("Conversation type")).toHaveValue(
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
    expect(screen.getByLabelText("Conversation type")).toHaveValue(
      "online_meeting",
    );
    fireEvent.click(screen.getByRole("button", { name: "Use linked context" }));
    expect(screen.getByLabelText("Company")).toHaveValue("company-3");
    expect(screen.getByLabelText("Conversation type")).toHaveValue(
      "phone_call",
    );
  });
});
