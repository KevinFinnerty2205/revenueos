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

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

function jsonResponse(body: object, status = 200): Response {
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
              total: 2,
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
        return Promise.resolve(jsonResponse({ fieldAuthority: {} }));
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
        return Promise.resolve(jsonResponse({ fieldAuthority: {} }));
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
            ownerUserId: null,
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
        return Promise.resolve(jsonResponse({ fieldAuthority: {} }));
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
          ownerUserId: null,
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
          return Promise.resolve(jsonResponse({ fieldAuthority: {} }));
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
});
