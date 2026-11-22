import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BusinessEntityForm } from "@/components/business-entity-form";

const router = vi.hoisted(() => ({ push: vi.fn() }));
const verifiedOrganisation = vi.hoisted(() => ({
  state: {
    status: "available" as "loading" | "available" | "unavailable",
    organisationId: "org-1" as string | null,
  },
}));

vi.mock("@/components/verified-organisation-context", () => ({
  useVerifiedOrganisation: () => verifiedOrganisation.state,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

const organisationId = "org-1";
const timestamp = "2026-07-24T10:00:00Z";

function companyResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: "company-1",
    organisationId,
    name: "Acme Australia",
    website: null,
    industry: null,
    location: null,
    employeeCount: null,
    status: "active",
    ownerUserId: "user-1",
    archivedAt: null,
    createdAt: timestamp,
    updatedAt: timestamp,
    ...overrides,
  };
}

function contactResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: "contact-1",
    organisationId,
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
    createdAt: timestamp,
    updatedAt: timestamp,
    ...overrides,
  };
}

function opportunityResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: "opportunity-1",
    organisationId,
    companyId: null,
    name: "Expansion",
    stage: "discovery",
    status: "open",
    estimatedValue: null,
    currency: null,
    expectedCloseDate: null,
    ownerUserId: "user-1",
    description: null,
    archivedAt: null,
    pipelineId: null,
    pipelineStageId: null,
    stageEnteredAt: null,
    stageTrackingStartedAt: null,
    actualCloseDate: null,
    outcomeReason: null,
    outcomeNote: null,
    outcomeProvenance: null,
    createdAt: timestamp,
    updatedAt: timestamp,
    ...overrides,
  };
}

function opportunityListItemResponse(overrides: Record<string, unknown> = {}) {
  const { outcomeNote: _outcomeNote, ...opportunity } = opportunityResponse();
  return {
    ...opportunity,
    companyName: null,
    ownerName: "Alex Morgan",
    latestMeetingId: null,
    latestMeetingDate: null,
    latestMeetingMomentum: null,
    latestNextBestAction: null,
    ...overrides,
  };
}

function taskResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: "task-1",
    organisationId,
    companyId: null,
    contactId: null,
    opportunityId: null,
    title: "Follow up",
    description: null,
    status: "open",
    priority: "medium",
    dueAt: null,
    assignedUserId: null,
    createdByUserId: "user-1",
    createdAt: timestamp,
    updatedAt: timestamp,
    ...overrides,
  };
}

function crmMember(overrides: Record<string, unknown> = {}) {
  return {
    organisationId,
    userId: "user-1",
    displayName: "Alex Morgan",
    active: true,
    canAssign: true,
    ...overrides,
  };
}

function crmRecordResponse(
  entityType: "account" | "contact" | "opportunity",
  entityId: string,
  fieldAuthority: Record<string, string> = {},
  overrides: Record<string, unknown> = {},
) {
  return {
    organisationId,
    entityType,
    entityId,
    archivedAt: null,
    fieldAuthority,
    ...overrides,
  };
}

function completeEntity(value: unknown, listItem = false): unknown {
  if (!value || typeof value !== "object" || Array.isArray(value)) return value;
  const record = value as Record<string, unknown>;
  const id = typeof record.id === "string" ? record.id : "";
  if ("firstName" in record || id.startsWith("contact-")) {
    return contactResponse(record);
  }
  if ("priority" in record || id.startsWith("task-")) {
    return taskResponse(record);
  }
  if ("stage" in record || id.startsWith("opportunity-")) {
    return listItem
      ? opportunityListItemResponse(record)
      : opportunityResponse(record);
  }
  if ("name" in record || id.startsWith("company-")) {
    return companyResponse(record);
  }
  return value;
}

function completeResponseBody(body: unknown): unknown {
  if (Array.isArray(body)) {
    return body.map((item) =>
      item && typeof item === "object" && "userId" in item
        ? crmMember(item as Record<string, unknown>)
        : completeEntity(item),
    );
  }
  if (!body || typeof body !== "object") return body;
  const record = body as Record<string, unknown>;
  if (Array.isArray(record.items) && "page" in record && "pageSize" in record) {
    return {
      organisationId,
      ...record,
      items: record.items.map((item) => completeEntity(item, true)),
    };
  }
  return completeEntity(body);
}

function jsonResponse(body: unknown, status = 200): Response {
  return rawJsonResponse(completeResponseBody(body), status);
}

function rawJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
} {
  let resolve: ((value: T) => void) | undefined;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return {
    promise,
    resolve(value: T) {
      if (!resolve) throw new Error("Deferred promise was not initialised.");
      resolve(value);
    },
  };
}

const emptyPage = {
  items: [],
  page: 1,
  pageSize: 100,
  total: 0,
  pages: 0,
};

describe("BusinessEntityForm", () => {
  afterEach(() => {
    router.push.mockReset();
    verifiedOrganisation.state = {
      status: "available",
      organisationId,
    };
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

  it("encodes a duplicate record ID as one route segment", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(rawJsonResponse([]))
      .mockResolvedValueOnce(
        rawJsonResponse(
          {
            code: "duplicate_record",
            message: "A matching account already exists.",
            requestId: "request-1",
            details: {
              entityType: "account",
              entityId: "company/one?private=true",
            },
          },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="companies" />);
    fireEvent.change(await screen.findByLabelText(/account name/i), {
      target: { value: "Acme Australia" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByRole("link", { name: "Open existing record" }),
    ).toHaveAttribute("href", "/companies/company%2Fone%3Fprivate%3Dtrue");
    expect(router.push).not.toHaveBeenCalled();
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
              archivedAt: null,
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
          {
            userId: "user-1",
            displayName: "Alex Morgan",
            active: true,
            canAssign: true,
          },
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
          archivedAt: null,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(crmRecordResponse("opportunity", "opportunity-1")),
      );
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

  it("prefills the account when an opportunity starts from an account", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input).includes("/api/v1/companies")) {
        return Promise.resolve(
          jsonResponse({
            items: [
              {
                id: "company-1",
                name: "Acme Australia",
                archivedAt: null,
              },
            ],
            page: 1,
            pageSize: 100,
            total: 1,
            pages: 1,
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BusinessEntityForm
        entity="opportunities"
        initialCompanyId="company-1"
      />,
    );

    expect(await screen.findByLabelText("Account")).toHaveValue("company-1");
  });

  it("appends an exact prefilled account beyond the first reference page", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/api/v1/companies/company-101")) {
        return Promise.resolve(
          jsonResponse({
            id: "company-101",
            name: "Beyond Page Account",
            archivedAt: null,
          }),
        );
      }
      if (path.includes("/api/v1/companies?pageSize=100")) {
        return Promise.resolve(
          jsonResponse({
            items: [
              {
                id: "company-1",
                name: "First Page Account",
                archivedAt: null,
              },
            ],
            page: 1,
            pageSize: 100,
            total: 101,
            pages: 2,
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BusinessEntityForm
        entity="opportunities"
        initialCompanyId="company-101"
      />,
    );

    expect(await screen.findByLabelText("Account")).toHaveValue("company-101");
    expect(
      screen.getByRole("option", { name: "Beyond Page Account" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/companies/company-101"),
      expect.any(Object),
    );
  });

  it("isolates create values when the prefilled account changes", async () => {
    const companyBPage = deferred<Response>();
    const accountACreate = deferred<Response>();
    let companyPageReads = 0;
    let createWrites = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.endsWith("/api/v1/opportunities")) {
        createWrites += 1;
        if (createWrites === 1) return accountACreate.promise;
        return Promise.resolve(jsonResponse({ id: "opportunity-b" }, 201));
      }
      if (url.includes("/api/v1/crm/members")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.includes("/api/v1/companies?pageSize=100")) {
        companyPageReads += 1;
        if (companyPageReads === 2) return companyBPage.promise;
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [
              {
                id: "company-a",
                name: "Account A",
                archivedAt: null,
              },
              {
                id: "company-b",
                name: "Account B",
                archivedAt: null,
              },
            ],
            total: 2,
            pages: 1,
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <BusinessEntityForm
        entity="opportunities"
        initialCompanyId="company-a"
      />,
    );
    expect(await screen.findByLabelText("Account")).toHaveValue("company-a");
    fireEvent.change(screen.getByLabelText(/Opportunity name/), {
      target: { value: "Account A private draft" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create opportunity" }));
    await waitFor(() => expect(createWrites).toBe(1));

    await act(async () => {
      rerender(
        <BusinessEntityForm
          entity="opportunities"
          initialCompanyId="company-b"
        />,
      );
      accountACreate.resolve(jsonResponse({ id: "opportunity-a" }, 201));
      await accountACreate.promise;
    });

    expect(screen.getByRole("status")).toHaveTextContent("Loading form");
    expect(
      screen.queryByDisplayValue("Account A private draft"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create opportunity" }),
    ).not.toBeInTheDocument();
    expect(router.push).not.toHaveBeenCalled();

    await act(async () => {
      companyBPage.resolve(
        jsonResponse({
          ...emptyPage,
          items: [{ id: "company-b", name: "Account B", archivedAt: null }],
          total: 1,
          pages: 1,
        }),
      );
      await companyBPage.promise;
    });

    expect(await screen.findByLabelText("Account")).toHaveValue("company-b");
    fireEvent.change(screen.getByLabelText(/Opportunity name/), {
      target: { value: "Account B opportunity" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create opportunity" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/opportunities/opportunity-b"),
    );
    const createCalls = fetchMock.mock.calls.filter(
      ([url, init]) =>
        String(url).endsWith("/api/v1/opportunities") &&
        init?.method === "POST",
    );
    expect(createCalls).toHaveLength(2);
    const createCall = createCalls[1];
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      companyId: "company-b",
      name: "Account B opportunity",
    });
    expect(String(createCall?.[1]?.body)).not.toContain("Account A");
  });

  it("does not offer archived relationship records", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/crm/members")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.includes("/api/v1/companies?pageSize=100")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [
              {
                id: "company-active",
                name: "Active Account",
                archivedAt: null,
              },
              {
                id: "company-archived",
                name: "Archived Account",
                archivedAt: "2026-11-21T00:00:00Z",
              },
            ],
            total: 2,
            pages: 1,
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="opportunities" />);

    expect(
      await screen.findByRole("option", { name: "Active Account" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("option", { name: "Archived Account" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    {
      label: "from another organisation",
      exactRecord: companyResponse({
        id: "company-target",
        organisationId: "org-2",
        name: "Foreign Account",
      }),
    },
    {
      label: "mismatched",
      exactRecord: {
        id: "company-other",
        name: "Wrong Account",
        archivedAt: null,
      },
    },
    {
      label: "archived",
      exactRecord: {
        id: "company-target",
        name: "Archived Account",
        archivedAt: "2026-11-21T00:00:00Z",
      },
    },
  ])(
    "fails closed when an exact relationship response is $label",
    async ({ exactRecord }) => {
      const fetchMock = vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/crm/members")) {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/api/v1/companies/company-target")) {
          return Promise.resolve(jsonResponse(exactRecord));
        }
        if (url.includes("/api/v1/companies?pageSize=100")) {
          return Promise.resolve(
            jsonResponse({
              ...emptyPage,
              items: [
                {
                  id: "company-first",
                  name: "First Account",
                  archivedAt: null,
                },
              ],
              total: 101,
              pages: 2,
            }),
          );
        }
        throw new Error(`Unexpected request: ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      render(
        <BusinessEntityForm
          entity="opportunities"
          initialCompanyId="company-target"
        />,
      );

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "A linked record could not be verified",
      );
      expect(
        screen.queryByRole("option", { name: exactRecord.name }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Create opportunity" }),
      ).not.toBeInTheDocument();
    },
  );

  it("loads active members and assigns a task in the create payload", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/crm/members")) {
        return Promise.resolve(
          jsonResponse([
            {
              userId: "user-active",
              displayName: "Alex Morgan",
              active: true,
              canAssign: true,
            },
            {
              userId: "user-inactive",
              displayName: "Casey Nguyen",
              active: false,
              canAssign: false,
            },
          ]),
        );
      }
      if (init?.method === "POST" && url.includes("/api/v1/tasks")) {
        return Promise.resolve(jsonResponse({ id: "task-1" }, 201));
      }
      return Promise.resolve(
        jsonResponse({
          items: [],
          page: 1,
          pageSize: 100,
          total: 0,
          pages: 0,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="tasks" />);

    expect(await screen.findByLabelText("Assignee")).toBeVisible();
    expect(screen.getByRole("option", { name: "Alex Morgan" })).toBeVisible();
    expect(
      screen.queryByRole("option", { name: "Casey Nguyen (inactive)" }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/task title/i), {
      target: { value: "Confirm renewal plan" },
    });
    fireEvent.change(screen.getByLabelText("Assignee"), {
      target: { value: "user-active" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create task" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.find((call) => call[1]?.method === "POST"),
      ).toBeDefined(),
    );
    const postCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "POST",
    );
    expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
      title: "Confirm renewal plan",
      assignedUserId: "user-active",
      status: "open",
      priority: "medium",
    });
    expect(router.push).toHaveBeenCalledWith("/tasks");
  });

  it("shows only task assignees the current member may choose", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/crm/members")) {
        return Promise.resolve(
          jsonResponse([
            {
              userId: "user-self",
              displayName: "Alex Morgan",
              active: true,
              canAssign: true,
            },
            {
              userId: "user-peer",
              displayName: "Casey Nguyen",
              active: true,
              canAssign: false,
            },
            {
              userId: "user-disabled",
              displayName: "Taylor Singh",
              active: false,
              canAssign: false,
            },
          ]),
        );
      }
      if (init?.method === "POST" && url.includes("/api/v1/tasks")) {
        return Promise.resolve(jsonResponse({ id: "task-1" }, 201));
      }
      return Promise.resolve(
        jsonResponse({
          items: [],
          page: 1,
          pageSize: 100,
          total: 0,
          pages: 0,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="tasks" />);

    const assignee = await screen.findByLabelText("Assignee");
    expect(screen.getByRole("option", { name: "Alex Morgan" })).toBeVisible();
    expect(
      screen.queryByRole("option", { name: /Casey Nguyen/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: /Taylor Singh/ }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/task title/i), {
      target: { value: "Member-owned follow-up" },
    });
    fireEvent.change(assignee, { target: { value: "user-self" } });
    fireEvent.click(screen.getByRole("button", { name: "Create task" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.find((call) => call[1]?.method === "POST"),
      ).toBeDefined(),
    );
    const postCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "POST",
    );
    expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
      assignedUserId: "user-self",
    });
  });

  it("retains an inactive task assignee without resending it and permits unassignment", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH" && url.endsWith("/api/v1/tasks/task-1")) {
        return Promise.resolve(jsonResponse({ id: "task-1" }));
      }
      if (url.includes("/api/v1/crm/members")) {
        return Promise.resolve(
          jsonResponse([
            {
              userId: "user-active",
              displayName: "Alex Morgan",
              active: true,
              canAssign: true,
            },
            {
              userId: "user-inactive",
              displayName: "Casey Nguyen",
              active: false,
              canAssign: false,
            },
          ]),
        );
      }
      if (url.endsWith("/api/v1/tasks/task-1")) {
        return Promise.resolve(
          jsonResponse({
            id: "task-1",
            title: "Confirm renewal plan",
            description: null,
            companyId: null,
            contactId: null,
            opportunityId: null,
            assignedUserId: "user-inactive",
            status: "open",
            priority: "medium",
            dueAt: null,
            archivedAt: null,
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          items: [],
          page: 1,
          pageSize: 100,
          total: 0,
          pages: 0,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="tasks" entityId="task-1" />);

    const assignee = await screen.findByLabelText("Assignee");
    expect(assignee).toHaveValue("user-inactive");
    expect(
      screen.getByRole("option", { name: "Casey Nguyen (inactive)" }),
    ).toBeDisabled();
    expect(screen.getByRole("option", { name: "Alex Morgan" })).toBeEnabled();

    fireEvent.change(screen.getByLabelText(/task title/i), {
      target: { value: "Confirm updated renewal plan" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter((call) => call[1]?.method === "PATCH"),
      ).toHaveLength(1),
    );
    const unchangedPatch = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "PATCH",
    );
    const unchangedPayload = JSON.parse(String(unchangedPatch?.[1]?.body));
    expect(unchangedPayload).toMatchObject({
      title: "Confirm updated renewal plan",
    });
    expect(unchangedPayload).not.toHaveProperty("assignedUserId");

    fireEvent.change(assignee, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter((call) => call[1]?.method === "PATCH"),
      ).toHaveLength(2),
    );
    const unassignPatch = fetchMock.mock.calls.filter(
      (call) => call[1]?.method === "PATCH",
    )[1];
    expect(JSON.parse(String(unassignPatch?.[1]?.body))).toMatchObject({
      assignedUserId: null,
    });
  });

  it("applies assignment authority to account owner choices", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          {
            userId: "user-self",
            displayName: "Alex Morgan",
            active: true,
            canAssign: true,
          },
          {
            userId: "user-peer",
            displayName: "Casey Nguyen",
            active: true,
            canAssign: false,
          },
        ]),
      ),
    );

    render(<BusinessEntityForm entity="companies" />);

    expect(await screen.findByLabelText("Owner")).toBeVisible();
    expect(screen.getByRole("option", { name: "Alex Morgan" })).toBeVisible();
    expect(
      screen.queryByRole("option", { name: /Casey Nguyen/ }),
    ).not.toBeInTheDocument();
  });

  it("keeps an unavailable account owner without revalidating an unchanged owner", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (
        init?.method === "PATCH" &&
        url.endsWith("/api/v1/companies/company-1")
      ) {
        return Promise.resolve(jsonResponse({ id: "company-1" }));
      }
      if (url.includes("/api/v1/crm/members")) {
        return Promise.resolve(
          jsonResponse([
            {
              userId: "user-self",
              displayName: "Alex Morgan",
              active: true,
              canAssign: true,
            },
            {
              userId: "user-former-owner",
              displayName: "Casey Nguyen",
              active: false,
              canAssign: false,
            },
          ]),
        );
      }
      if (url.endsWith("/api/v1/companies/company-1")) {
        return Promise.resolve(
          jsonResponse({
            id: "company-1",
            name: "Acme Australia",
            website: null,
            industry: null,
            location: null,
            employeeCount: null,
            ownerUserId: "user-former-owner",
            status: "active",
            updatedAt: "2026-10-31T03:00:00Z",
            archivedAt: null,
          }),
        );
      }
      if (url.endsWith("/api/v1/crm/records/account/company-1")) {
        return Promise.resolve(
          jsonResponse(crmRecordResponse("account", "company-1")),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="companies" entityId="company-1" />);

    const owner = await screen.findByLabelText("Owner");
    expect(owner).toHaveValue("user-former-owner");
    expect(
      screen.getByRole("option", { name: "Casey Nguyen (inactive)" }),
    ).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/account name/i), {
      target: { value: "Acme Australia Updated" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save account" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.find((call) => call[1]?.method === "PATCH"),
      ).toBeDefined(),
    );
    const patchCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "PATCH",
    );
    const payload = JSON.parse(String(patchCall?.[1]?.body));
    expect(payload).toMatchObject({
      name: "Acme Australia Updated",
      expectedUpdatedAt: "2026-10-31T03:00:00Z",
    });
    expect(payload).not.toHaveProperty("ownerUserId");
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
            items: [
              {
                id: "company-1",
                name: "Acme Australia",
                archivedAt: null,
              },
            ],
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
        return Promise.resolve(
          jsonResponse(crmRecordResponse("contact", "contact-1")),
        );
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
          archivedAt: null,
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
    fireEvent.click(screen.getByRole("button", { name: "Save person" }));

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
            items: [
              {
                id: "company-1",
                name: "Northstar Facilities",
                archivedAt: null,
              },
            ],
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
          jsonResponse(crmRecordResponse("contact", "contact-1")),
        );
      return Promise.resolve(
        jsonResponse({
          id: "contact-1",
          companyId: "company-1",
          firstName: "Jane",
          lastName: "Smith",
          email: "jane.smith@northstar-facilities.example",
          status: "active",
          archivedAt: null,
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
            items: [
              {
                id: "company-1",
                name: "Acme Australia",
                archivedAt: null,
              },
            ],
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
          jsonResponse(
            crmRecordResponse("contact", "contact-1", {
              first_name: "crm_authoritative",
            }),
          ),
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
          archivedAt: null,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BusinessEntityForm entity="contacts" entityId="contact-1" />);
    expect(await screen.findByLabelText(/First name/)).toBeDisabled();
    expect(
      screen.getByText("CRM controlled · read-only in Oryntela"),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Save person" }));

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

  it("isolates task values and late saves when the edited task changes", async () => {
    const taskBLoad = deferred<Response>();
    const taskASave = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH" && url.endsWith("/api/v1/tasks/task-a")) {
        return taskASave.promise;
      }
      if (init?.method === "PATCH" && url.endsWith("/api/v1/tasks/task-b")) {
        return Promise.resolve(jsonResponse({ id: "task-b" }));
      }
      if (url.endsWith("/api/v1/tasks/task-a")) {
        return Promise.resolve(
          jsonResponse({
            id: "task-a",
            title: "Task A private title",
            description: "Task A private description",
            companyId: null,
            contactId: null,
            opportunityId: null,
            assignedUserId: null,
            status: "open",
            priority: "high",
            dueAt: null,
            archivedAt: null,
          }),
        );
      }
      if (url.endsWith("/api/v1/tasks/task-b")) return taskBLoad.promise;
      if (url.includes("/api/v1/crm/members")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.includes("?pageSize=100")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <BusinessEntityForm entity="tasks" entityId="task-a" />,
    );
    expect(
      await screen.findByDisplayValue("Task A private title"),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText(/task title/i), {
      target: { value: "Task A unsaved sentinel" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/api/v1/tasks/task-a") &&
            init?.method === "PATCH",
        ),
      ).toBe(true),
    );

    await act(async () => {
      rerender(<BusinessEntityForm entity="tasks" entityId="task-b" />);
      taskASave.resolve(jsonResponse({ id: "task-a" }));
      await taskASave.promise;
      await Promise.resolve();
    });

    expect(screen.getByRole("status")).toHaveTextContent("Loading form");
    expect(
      screen.queryByDisplayValue("Task A private title"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("Task A unsaved sentinel"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("Task A private description"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save task" }),
    ).not.toBeInTheDocument();
    expect(router.push).not.toHaveBeenCalled();

    await act(async () => {
      taskBLoad.resolve(
        jsonResponse({
          id: "task-b",
          title: "Task B title",
          description: "Task B description",
          companyId: null,
          contactId: null,
          opportunityId: null,
          assignedUserId: null,
          status: "in_progress",
          priority: "medium",
          dueAt: null,
          archivedAt: null,
        }),
      );
      await taskBLoad.promise;
    });
    expect(await screen.findByDisplayValue("Task B title")).toBeVisible();
    fireEvent.change(screen.getByLabelText(/task title/i), {
      target: { value: "Task B updated" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/tasks"));
    const taskBPatch = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/api/v1/tasks/task-b") &&
        init?.method === "PATCH",
    );
    expect(taskBPatch).toBeDefined();
    expect(JSON.parse(String(taskBPatch?.[1]?.body))).toMatchObject({
      title: "Task B updated",
      description: "Task B description",
      status: "in_progress",
      priority: "medium",
    });
    expect(String(taskBPatch?.[1]?.body)).not.toContain("Task A");
  });

  it("uses only the current account values and lock after an edit transition", async () => {
    const companyBLoad = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (
        init?.method === "PATCH" &&
        url.endsWith("/api/v1/companies/company-b")
      ) {
        return Promise.resolve(jsonResponse({ id: "company-b" }));
      }
      if (url.includes("/api/v1/crm/members")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/api/v1/companies/company-a")) {
        return Promise.resolve(
          jsonResponse({
            id: "company-a",
            name: "Account A private name",
            website: null,
            industry: "Account A private industry",
            location: null,
            employeeCount: null,
            ownerUserId: "user-1",
            status: "active",
            updatedAt: "2026-10-01T00:00:00Z",
            archivedAt: null,
          }),
        );
      }
      if (url.endsWith("/api/v1/companies/company-b")) {
        return companyBLoad.promise;
      }
      if (url.includes("/api/v1/crm/records/account/")) {
        return Promise.resolve(
          jsonResponse(
            crmRecordResponse(
              "account",
              url.endsWith("company-a") ? "company-a" : "company-b",
            ),
          ),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <BusinessEntityForm entity="companies" entityId="company-a" />,
    );
    expect(
      await screen.findByDisplayValue("Account A private name"),
    ).toBeVisible();

    rerender(<BusinessEntityForm entity="companies" entityId="company-b" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading form");
    expect(
      screen.queryByDisplayValue("Account A private name"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("Account A private industry"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save account" }),
    ).not.toBeInTheDocument();

    await act(async () => {
      companyBLoad.resolve(
        jsonResponse({
          id: "company-b",
          name: "Account B name",
          website: "https://b.example",
          industry: "Services",
          location: "Sydney",
          employeeCount: 25,
          ownerUserId: "user-1",
          status: "active",
          updatedAt: "2026-11-21T00:00:00Z",
          archivedAt: null,
        }),
      );
      await companyBLoad.promise;
    });
    expect(await screen.findByDisplayValue("Account B name")).toBeVisible();
    fireEvent.change(screen.getByLabelText(/account name/i), {
      target: { value: "Account B updated" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save account" }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/companies"));
    const companyBPatch = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/api/v1/companies/company-b") &&
        init?.method === "PATCH",
    );
    expect(companyBPatch).toBeDefined();
    expect(JSON.parse(String(companyBPatch?.[1]?.body))).toMatchObject({
      name: "Account B updated",
      website: "https://b.example",
      industry: "Services",
      location: "Sydney",
      employeeCount: 25,
      status: "active",
      expectedUpdatedAt: "2026-11-21T00:00:00Z",
    });
    expect(String(companyBPatch?.[1]?.body)).not.toContain("Account A");
  });

  it.each([
    {
      label: "from another organisation",
      record: companyResponse({
        id: "company-b",
        organisationId: "org-2",
        name: "Foreign Account B private name",
      }),
    },
    {
      label: "mismatched",
      record: {
        id: "company-a",
        name: "Account A private name",
        archivedAt: null,
      },
    },
    {
      label: "archived",
      record: {
        id: "company-b",
        name: "Archived Account B private name",
        archivedAt: "2026-11-21T00:00:00Z",
      },
    },
  ])(
    "fails closed when the edited record response is $label",
    async ({ record }) => {
      const fetchMock = vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/crm/members")) {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/api/v1/companies/company-b")) {
          return Promise.resolve(jsonResponse(record));
        }
        if (url.endsWith("/api/v1/crm/records/account/company-b")) {
          return Promise.resolve(
            jsonResponse(crmRecordResponse("account", "company-b")),
          );
        }
        throw new Error(`Unexpected request: ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      render(<BusinessEntityForm entity="companies" entityId="company-b" />);

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "The requested record could not be verified",
      );
      expect(screen.queryByDisplayValue(record.name)).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Save account" }),
      ).not.toBeInTheDocument();
    },
  );

  it("does not request private form data until the organisation is verified", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    verifiedOrganisation.state = {
      status: "loading",
      organisationId: null,
    };

    const { rerender } = render(<BusinessEntityForm entity="companies" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Verifying your secure workspace",
    );
    expect(fetchMock).not.toHaveBeenCalled();

    verifiedOrganisation.state = {
      status: "unavailable",
      organisationId: null,
    };
    rerender(<BusinessEntityForm entity="companies" />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "organisation could not be verified",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    {
      label: "wrong envelope organisation",
      page: {
        organisationId: "org-2",
        items: [companyResponse()],
        page: 1,
        pageSize: 100,
        total: 1,
        pages: 1,
      },
    },
    {
      label: "one foreign item",
      page: {
        organisationId,
        items: [
          companyResponse(),
          companyResponse({ id: "company-2", organisationId: "org-2" }),
        ],
        page: 1,
        pageSize: 100,
        total: 2,
        pages: 1,
      },
    },
  ])("rejects a $label reference page atomically", async ({ page }) => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/crm/members")) {
          return Promise.resolve(rawJsonResponse([]));
        }
        if (url.includes("/api/v1/companies?pageSize=100")) {
          return Promise.resolve(rawJsonResponse(page));
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    render(<BusinessEntityForm entity="opportunities" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "relationship list could not be verified",
    );
    expect(screen.queryByText("Acme Australia")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create opportunity" }),
    ).not.toBeInTheDocument();
  });

  it("rejects a mixed-organisation CRM member list atomically", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/crm/members")) {
          return Promise.resolve(
            rawJsonResponse([
              crmMember(),
              crmMember({ userId: "user-2", organisationId: "org-2" }),
            ]),
          );
        }
        if (url.includes("?pageSize=100")) {
          return Promise.resolve(
            rawJsonResponse({ ...emptyPage, organisationId }),
          );
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    render(<BusinessEntityForm entity="tasks" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "member list could not be verified",
    );
    expect(screen.queryByText("Alex Morgan")).not.toBeInTheDocument();
  });

  it.each([
    {
      label: "wrong organisation",
      response: crmRecordResponse(
        "account",
        "company-1",
        {},
        {
          organisationId: "org-2",
        },
      ),
    },
    {
      label: "wrong entity type",
      response: crmRecordResponse("contact", "company-1"),
    },
    {
      label: "wrong entity ID",
      response: crmRecordResponse("account", "company-2"),
    },
    {
      label: "archived record",
      response: crmRecordResponse(
        "account",
        "company-1",
        {},
        {
          archivedAt: timestamp,
        },
      ),
    },
    {
      label: "invalid authority",
      response: crmRecordResponse("account", "company-1", {
        name: "external_wins",
      }),
    },
  ])("rejects CRM authority with $label", async ({ response }) => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/crm/members")) {
          return Promise.resolve(rawJsonResponse([]));
        }
        if (url.endsWith("/api/v1/companies/company-1")) {
          return Promise.resolve(jsonResponse(companyResponse()));
        }
        if (url.endsWith("/api/v1/crm/records/account/company-1")) {
          return Promise.resolve(rawJsonResponse(response));
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    render(<BusinessEntityForm entity="companies" entityId="company-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "record authority could not be verified",
    );
    expect(
      screen.queryByRole("button", { name: "Save account" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    {
      label: "wrong organisation",
      response: companyResponse({ organisationId: "org-2" }),
    },
    {
      label: "an invalid created ID",
      response: companyResponse({ id: "" }),
    },
    {
      label: "an incomplete body",
      response: { id: "company-1", organisationId },
    },
  ])(
    "rejects a successful create response with $label",
    async ({ response }) => {
      vi.stubGlobal(
        "fetch",
        vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
          const url = String(input);
          if (url.includes("/api/v1/crm/members")) {
            return Promise.resolve(rawJsonResponse([]));
          }
          if (init?.method === "POST") {
            return Promise.resolve(rawJsonResponse(response, 201));
          }
          throw new Error(`Unexpected request: ${url}`);
        }),
      );

      render(<BusinessEntityForm entity="companies" />);
      fireEvent.change(await screen.findByLabelText(/account name/i), {
        target: { value: "Invalid save response" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Create account" }));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "saved record could not be verified",
      );
      expect(router.push).not.toHaveBeenCalled();
    },
  );

  it.each([
    {
      label: "wrong organisation",
      response: companyResponse({ organisationId: "org-2" }),
    },
    {
      label: "wrong record ID",
      response: companyResponse({ id: "company-2" }),
    },
    {
      label: "archived record",
      response: companyResponse({ archivedAt: timestamp }),
    },
  ])("rejects a successful edit response with $label", async ({ response }) => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/v1/crm/members")) {
          return Promise.resolve(rawJsonResponse([]));
        }
        if (init?.method === "PATCH") {
          return Promise.resolve(rawJsonResponse(response));
        }
        if (url.endsWith("/api/v1/companies/company-1")) {
          return Promise.resolve(jsonResponse(companyResponse()));
        }
        if (url.endsWith("/api/v1/crm/records/account/company-1")) {
          return Promise.resolve(
            rawJsonResponse(crmRecordResponse("account", "company-1")),
          );
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    render(<BusinessEntityForm entity="companies" entityId="company-1" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Save account" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "saved record could not be verified",
    );
    expect(router.push).not.toHaveBeenCalled();
  });

  it("encodes a verified created Opportunity ID as one route segment", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/v1/crm/members")) {
          return Promise.resolve(rawJsonResponse([]));
        }
        if (url.includes("/api/v1/companies?pageSize=100")) {
          return Promise.resolve(
            rawJsonResponse({ ...emptyPage, organisationId }),
          );
        }
        if (init?.method === "POST") {
          return Promise.resolve(
            rawJsonResponse(
              opportunityResponse({ id: "opportunity/one?private=true" }),
              201,
            ),
          );
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    render(<BusinessEntityForm entity="opportunities" />);
    fireEvent.change(await screen.findByLabelText(/Opportunity name/i), {
      target: { value: "Encoded route" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create opportunity" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith(
        "/opportunities/opportunity%2Fone%3Fprivate%3Dtrue",
      ),
    );
  });

  it("does not navigate when an organisation changes during a save", async () => {
    const save = deferred<Response>();
    let memberReads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/crm/members")) {
        memberReads += 1;
        return Promise.resolve(rawJsonResponse([]));
      }
      if (init?.method === "POST") return save.promise;
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(<BusinessEntityForm entity="companies" />);
    fireEvent.change(await screen.findByLabelText(/account name/i), {
      target: { value: "Organisation A draft" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
      ).toBe(true),
    );

    verifiedOrganisation.state = {
      status: "available",
      organisationId: "org-2",
    };
    rerender(<BusinessEntityForm entity="companies" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading form");

    await act(async () => {
      save.resolve(
        rawJsonResponse(companyResponse({ name: "Organisation A draft" }), 201),
      );
      await save.promise;
    });

    expect(await screen.findByLabelText(/account name/i)).toHaveValue("");
    expect(
      screen.queryByDisplayValue("Organisation A draft"),
    ).not.toBeInTheDocument();
    expect(router.push).not.toHaveBeenCalled();
    expect(memberReads).toBe(2);
  });
});
