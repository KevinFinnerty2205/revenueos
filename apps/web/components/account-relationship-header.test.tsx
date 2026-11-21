import type { Company, Contact, EntityPage } from "@revenueos/shared";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountRelationshipHeader } from "@/components/account-relationship-header";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
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

const secondCompany: Company = {
  ...company,
  id: "company-two",
  name: "Harbour Health",
  website: "https://harbour.example.test",
  industry: "Healthcare",
  location: "Melbourne",
};

const secondParticipants: Contact[] = [
  {
    ...participants[0],
    id: "contact-2",
    companyId: secondCompany.id,
    firstName: "Alex",
    lastName: "Morgan",
    email: "alex@example.test",
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

    render(<AccountRelationshipHeader companyId={company.id} />);

    expect(
      await screen.findByText(
        "Participants linked to future conversations will appear here.",
      ),
    ).toBeVisible();
    expect(screen.getByText("0 people")).toBeVisible();
  });

  it("keeps account identity visible when participants are unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/contacts")
            ? jsonResponse({ detail: "sensitive participant failure" }, 503)
            : jsonResponse(company),
        ),
      ),
    );

    render(<AccountRelationshipHeader companyId={company.id} />);

    expect(
      await screen.findByRole("heading", { name: "Northstar Facilities" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "People linked to this account are temporarily unavailable.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("0 people")).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "Participants linked to future conversations will appear here.",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("sensitive participant failure"),
    ).not.toBeInTheDocument();
  });

  it("renders account identity before participant loading completes", async () => {
    const participantRequest = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes("/contacts")
          ? participantRequest.promise
          : Promise.resolve(jsonResponse(company)),
      ),
    );

    render(<AccountRelationshipHeader companyId={company.id} />);

    expect(
      await screen.findByRole("heading", { name: "Northstar Facilities" }),
    ).toBeVisible();
    expect(
      screen.getByText("Loading people linked to this account…"),
    ).toBeVisible();
    expect(screen.queryByText("0 people")).not.toBeInTheDocument();

    participantRequest.resolve(jsonResponse(contactPage(participants)));

    expect(await screen.findByText("Jordan Lee")).toBeVisible();
    expect(screen.getByText("1 person")).toBeVisible();
    expect(
      screen.queryByText("Loading people linked to this account…"),
    ).not.toBeInTheDocument();
  });

  it("keeps required account failure authoritative when participants load", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/contacts")
            ? jsonResponse(contactPage(participants))
            : jsonResponse({}, 503),
        ),
      ),
    );

    render(<AccountRelationshipHeader companyId={company.id} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Oryntela couldn’t load this account.",
    );
    expect(
      screen.queryByRole("heading", { name: "Northstar Facilities" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Jordan Lee")).not.toBeInTheDocument();
  });

  it.each([
    ["mismatched", secondCompany],
    [
      "archived",
      {
        ...company,
        archivedAt: "2026-11-02T00:00:00Z",
      },
    ],
  ])(
    "fails closed when the required account response is %s",
    async (_case, invalidCompany) => {
      vi.stubGlobal(
        "fetch",
        vi.fn((input: RequestInfo | URL) =>
          Promise.resolve(
            jsonResponse(
              String(input).includes("/contacts")
                ? contactPage([])
                : invalidCompany,
            ),
          ),
        ),
      );

      render(<AccountRelationshipHeader companyId={company.id} />);

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Oryntela couldn’t load this account.",
      );
      expect(screen.getByRole("alert")).toHaveTextContent(
        "This account could not be loaded.",
      );
      expect(
        screen.queryByRole("heading", { name: invalidCompany.name }),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("0 people")).not.toBeInTheDocument();
    },
  );

  it.each([
    ["another account", secondParticipants],
    [
      "an archived record",
      [
        {
          ...participants[0],
          archivedAt: "2026-11-02T00:00:00Z",
        },
      ],
    ],
  ])(
    "treats participant results containing %s as unavailable",
    async (_case, invalidParticipants) => {
      vi.stubGlobal(
        "fetch",
        vi.fn((input: RequestInfo | URL) =>
          Promise.resolve(
            jsonResponse(
              String(input).includes("/contacts")
                ? contactPage(invalidParticipants)
                : company,
            ),
          ),
        ),
      );

      render(<AccountRelationshipHeader companyId={company.id} />);

      expect(
        await screen.findByRole("heading", { name: "Northstar Facilities" }),
      ).toBeVisible();
      expect(
        screen.getByText(
          "People linked to this account are temporarily unavailable.",
        ),
      ).toBeVisible();
      for (const participant of invalidParticipants) {
        expect(
          screen.queryByText(
            `${participant.firstName} ${participant.lastName}`,
          ),
        ).not.toBeInTheDocument();
      }
      expect(screen.queryByText("0 people")).not.toBeInTheDocument();
      expect(
        screen.queryByText(
          "Participants linked to future conversations will appear here.",
        ),
      ).not.toBeInTheDocument();
    },
  );

  it("hides the previous account immediately and shows the new failure", async () => {
    const secondCompanyRequest = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/contacts")) {
          return Promise.resolve(jsonResponse(contactPage([])));
        }
        if (url.includes("company-two")) return secondCompanyRequest.promise;
        return Promise.resolve(jsonResponse(company));
      }),
    );

    const { rerender } = render(
      <AccountRelationshipHeader companyId={company.id} />,
    );
    expect(
      await screen.findByRole("heading", { name: "Northstar Facilities" }),
    ).toBeVisible();

    rerender(<AccountRelationshipHeader companyId={secondCompany.id} />);

    expect(
      screen.queryByRole("heading", { name: "Northstar Facilities" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Loading account relationship")).toBeVisible();

    secondCompanyRequest.resolve(jsonResponse({}, 503));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Oryntela couldn’t load this account.",
    );
    expect(
      screen.queryByRole("heading", { name: "Northstar Facilities" }),
    ).not.toBeInTheDocument();
  });

  it("ignores a delayed participant response from the previous account", async () => {
    const firstParticipantsRequest = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/contacts") && url.includes("company%2Fone")) {
          return firstParticipantsRequest.promise;
        }
        if (url.includes("/contacts")) {
          return Promise.resolve(jsonResponse(contactPage(secondParticipants)));
        }
        return Promise.resolve(
          jsonResponse(url.includes("company-two") ? secondCompany : company),
        );
      }),
    );

    const { rerender } = render(
      <AccountRelationshipHeader companyId={company.id} />,
    );
    expect(
      await screen.findByRole("heading", { name: "Northstar Facilities" }),
    ).toBeVisible();
    expect(
      screen.getByText("Loading people linked to this account…"),
    ).toBeVisible();

    rerender(<AccountRelationshipHeader companyId={secondCompany.id} />);

    expect(
      await screen.findByRole("heading", { name: "Harbour Health" }),
    ).toBeVisible();
    expect(await screen.findByText("Alex Morgan")).toBeVisible();

    await act(async () => {
      firstParticipantsRequest.resolve(jsonResponse(contactPage(participants)));
      await firstParticipantsRequest.promise;
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(screen.getByText("Alex Morgan")).toBeVisible();
    expect(screen.queryByText("Jordan Lee")).not.toBeInTheDocument();
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

    render(<AccountRelationshipHeader companyId={company.id} />);

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
        String(input).includes("/api/v1/companies/company%2Fone"),
      ),
    ).toBe(true);
  });
});
