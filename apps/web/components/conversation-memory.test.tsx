import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationMemory as ConversationMemoryComponent } from "@/components/conversation-memory";

function ConversationMemory({
  interactionId,
  companyId,
}: {
  interactionId: string;
  companyId: string | null;
}) {
  return (
    <ConversationMemoryComponent
      interactionId={interactionId}
      organisationId="organisation-1"
      companyId={companyId}
    />
  );
}

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

const thread = {
  id: "thread-expansion",
  organisationId: "organisation-1",
  companyId: "company-1",
  name: "Expansion",
  status: "active",
  interactionCount: 2,
  lastInteractionAt: "2026-04-21T02:00:00Z",
  lockVersion: 1,
  createdByUserId: "user-1",
  updatedByUserId: "user-1",
  createdAt: "2026-01-15T02:00:00Z",
  updatedAt: "2026-04-21T02:00:00Z",
} as const;

const definition = {
  id: null,
  key: "bant",
  name: "BANT",
  description: "Evidence-backed coverage.",
  version: 1,
  standard: true,
  status: "active",
  fieldCount: 1,
  fields: [],
  createdAt: null,
} as const;

const coverage = {
  stateCounts: {
    confirmed: 0,
    partiallySupported: 0,
    unknown: 0,
    conflicting: 1,
    stale: 0,
  },
  items: [
    {
      fieldKey: "timing",
      displayName: "Timing",
      explanation: "Target timing.",
      required: true,
      state: "conflicting",
      conclusion:
        "Current valid sources disagree. Oryntela has not selected either interpretation.",
      sources: [
        {
          sourceType: "interaction_intelligence",
          sourceId: "snapshot-april",
          itemKey: "item:0:timing",
          label: "Reported by you",
          origin: "salesperson_reported",
          supportedAt: "2026-04-21T02:00:00Z",
          sourceClassification: "Reviewed salesperson report",
        },
      ],
      conflicts: [],
      lastSupportedAt: "2026-04-21T02:00:00Z",
      freshness: "current",
      suggestedQuestion: "What date is driving the decision?",
      stageExpectation: "evaluation",
      reviews: [],
    },
  ],
  sourceConversations: [
    {
      sourceId: "snapshot-april",
      interactionId: "interaction-1",
      interactionTitle: "April expansion follow-up",
      occurredAt: "2026-04-21T02:00:00Z",
    },
  ],
} as const;

const initiativeHistory = {
  items: [
    {
      interactionId: "interaction-march",
      title: "March expansion review",
      interactionType: "online_meeting",
      lifecycleStatus: "completed",
      occurredAt: "2026-03-18T02:00:00Z",
    },
    {
      interactionId: "interaction-january",
      title: "January expansion discovery",
      interactionType: "phone_call",
      lifecycleStatus: "completed",
      occurredAt: "2026-01-15T02:00:00Z",
    },
  ],
  total: 2,
  truncated: false,
} as const;

function memory(assigned: boolean) {
  return {
    organisationId: "organisation-1",
    state: "current",
    safeMessage: assigned
      ? "Current-conversation coverage is separate from the user-confirmed initiative history."
      : "Confirm or create an initiative before cumulative history is used.",
    definition,
    assignment: {
      interactionId: "interaction-1",
      thread: assigned ? thread : null,
      lockVersion: assigned ? 1 : 0,
      confirmationKind: assigned ? "user_confirmed" : null,
      confirmedByUserId: assigned ? "user-1" : null,
      confirmedAt: assigned ? "2026-04-21T02:05:00Z" : null,
    },
    suggestions: assigned
      ? []
      : [
          {
            thread,
            score: 4,
            reasons: ["Same company", "1 participant in common"],
          },
        ],
    currentConversation: coverage,
    confirmedThread: assigned ? coverage : null,
    confirmedInitiativeHistory: assigned
      ? initiativeHistory
      : { items: [], total: 0, truncated: false },
    generatedAt: "2026-10-31T00:00:00Z",
  };
}

function interactionMemory(
  interactionId: string,
  assigned: boolean,
  titlePrefix: string,
) {
  const value = memory(assigned);
  return {
    ...value,
    assignment: {
      ...value.assignment,
      interactionId,
    },
    currentConversation: {
      ...value.currentConversation,
      sourceConversations: value.currentConversation.sourceConversations.map(
        (source) => ({ ...source, interactionId }),
      ),
    },
    confirmedInitiativeHistory: {
      ...value.confirmedInitiativeHistory,
      items: value.confirmedInitiativeHistory.items.map((item) => ({
        ...item,
        title: `${titlePrefix} ${item.title}`,
      })),
    },
  };
}

afterEach(() => vi.restoreAllMocks());

describe("ConversationMemory", () => {
  it("hides confirmed memory synchronously when the conversation context changes", async () => {
    const interactionB = createDeferred<Response>();
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/interaction-a/conversation-memory")) {
        return Promise.resolve(
          jsonResponse(interactionMemory("interaction-a", true, "A")),
        );
      }
      if (url.includes("/interaction-b/conversation-memory")) {
        return interactionB.promise;
      }
      if (url.endsWith("/conversation-threads")) {
        return Promise.resolve(jsonResponse([thread]));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const view = render(
      <ConversationMemory
        interactionId="interaction-a"
        companyId="company-a"
      />,
    );

    expect(
      await screen.findByRole("link", { name: "A March expansion review" }),
    ).toBeVisible();

    view.rerender(
      <ConversationMemory
        interactionId="interaction-b"
        companyId="company-b"
      />,
    );

    expect(
      screen.queryByRole("link", { name: "A March expansion review" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Loading conversation memory…")).toBeVisible();

    interactionB.resolve(
      jsonResponse(interactionMemory("interaction-b", true, "B")),
    );
    expect(
      await screen.findByRole("link", { name: "B March expansion review" }),
    ).toBeVisible();
  });

  it("ignores a late authoritative-memory response from the previous conversation", async () => {
    const interactionA = createDeferred<Response>();
    const fetchMock = vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/interaction-a/conversation-memory")) {
        return interactionA.promise;
      }
      if (url.includes("/interaction-b/conversation-memory")) {
        return Promise.resolve(
          jsonResponse(interactionMemory("interaction-b", true, "B")),
        );
      }
      if (url.endsWith("/conversation-threads")) {
        return Promise.resolve(jsonResponse([thread]));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const view = render(
      <ConversationMemory
        interactionId="interaction-a"
        companyId="company-a"
      />,
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(
          "/interactions/interaction-a/conversation-memory",
        ),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );

    view.rerender(
      <ConversationMemory
        interactionId="interaction-b"
        companyId="company-b"
      />,
    );
    expect(
      await screen.findByRole("link", { name: "B March expansion review" }),
    ).toBeVisible();

    interactionA.resolve(
      jsonResponse(interactionMemory("interaction-a", true, "A")),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("link", { name: "A March expansion review" }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("link", { name: "B March expansion review" }),
    ).toBeVisible();
  });

  it("rejects authoritative memory for a different conversation", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/interaction-b/conversation-memory")) {
        return jsonResponse(interactionMemory("interaction-a", true, "A"));
      }
      if (url.endsWith("/conversation-threads")) return jsonResponse([thread]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-b"
        companyId="company-b"
      />,
    );

    expect(
      await screen.findByText(/conversation memory returned an unexpected/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "A March expansion review" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    [
      "a different organisation",
      { ...memory(true), organisationId: "organisation-2" },
    ],
    [
      "an assignment from a different organisation",
      {
        ...memory(true),
        assignment: {
          ...memory(true).assignment,
          thread: { ...thread, organisationId: "organisation-2" },
        },
      },
    ],
    [
      "a suggestion from a different organisation",
      {
        ...memory(false),
        suggestions: [
          {
            ...memory(false).suggestions[0],
            thread: { ...thread, organisationId: "organisation-2" },
          },
        ],
      },
    ],
    [
      "current coverage from another interaction",
      {
        ...memory(true),
        currentConversation: {
          ...coverage,
          sourceConversations: [
            {
              ...coverage.sourceConversations[0],
              interactionId: "interaction-2",
            },
          ],
        },
      },
    ],
  ])("rejects authoritative memory containing %s", async (_, payload) => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory")) return jsonResponse(payload);
      if (url.endsWith("/conversation-threads")) return jsonResponse([thread]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByText(/conversation memory returned an unexpected/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "March expansion review" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Expansion")).not.toBeInTheDocument();
  });

  it("does not refresh the previous conversation after its assignment settles late", async () => {
    const assignment = createDeferred<Response>();
    let interactionAReads = 0;
    vi.spyOn(global, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/interaction-a/conversation-memory")) {
        interactionAReads += 1;
        return Promise.resolve(
          jsonResponse(interactionMemory("interaction-a", false, "A")),
        );
      }
      if (
        url.includes("/interaction-a/thread-assignment") &&
        init?.method === "PUT"
      ) {
        return assignment.promise;
      }
      if (url.includes("/interaction-b/conversation-memory")) {
        return Promise.resolve(
          jsonResponse(interactionMemory("interaction-b", true, "B")),
        );
      }
      if (url.endsWith("/conversation-threads") && !init?.method) {
        return Promise.resolve(jsonResponse([thread]));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const view = render(
      <ConversationMemory
        interactionId="interaction-a"
        companyId="company-a"
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Expansion · Same company, 1 participant in common",
      }),
    );

    view.rerender(
      <ConversationMemory
        interactionId="interaction-b"
        companyId="company-b"
      />,
    );
    expect(
      await screen.findByRole("link", { name: "B March expansion review" }),
    ).toBeVisible();

    assignment.resolve(
      jsonResponse(interactionMemory("interaction-a", true, "A").assignment),
    );
    await waitFor(() => expect(interactionAReads).toBe(1));
    expect(
      screen.getByRole("link", { name: "B March expansion review" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "A March expansion review" }),
    ).not.toBeInTheDocument();
  });

  it("does not refresh or clear the current conversation after an older initiative creation settles", async () => {
    const createdThread = createDeferred<Response>();
    let interactionAReads = 0;
    vi.spyOn(global, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/interaction-a/conversation-memory")) {
        interactionAReads += 1;
        return Promise.resolve(
          jsonResponse(interactionMemory("interaction-a", false, "A")),
        );
      }
      if (url.endsWith("/conversation-threads") && init?.method === "POST") {
        return createdThread.promise;
      }
      if (url.includes("/interaction-b/conversation-memory")) {
        return Promise.resolve(
          jsonResponse(interactionMemory("interaction-b", true, "B")),
        );
      }
      if (url.endsWith("/conversation-threads") && !init?.method) {
        return Promise.resolve(jsonResponse([thread]));
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const view = render(
      <ConversationMemory
        interactionId="interaction-a"
        companyId="company-a"
      />,
    );
    const input = await screen.findByPlaceholderText(
      "For example, APAC renewal programme",
    );
    fireEvent.change(input, { target: { value: "A private initiative" } });
    fireEvent.click(
      screen.getByRole("button", { name: "Create and confirm initiative" }),
    );

    view.rerender(
      <ConversationMemory
        interactionId="interaction-b"
        companyId="company-b"
      />,
    );
    expect(
      await screen.findByRole("link", { name: "B March expansion review" }),
    ).toBeVisible();

    createdThread.resolve(jsonResponse(thread, 201));
    await waitFor(() => expect(interactionAReads).toBe(1));
    expect(
      screen.getByRole("link", { name: "B March expansion review" }),
    ).toBeVisible();
    expect(
      screen.getByPlaceholderText("For example, APAC renewal programme"),
    ).toHaveValue("");
  });

  it("keeps confirmed initiative history visible when the initiative directory is unavailable", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory"))
        return jsonResponse(memory(true));
      if (url.endsWith("/conversation-threads"))
        return jsonResponse({ message: "Directory unavailable" }, 503);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByRole("link", { name: "March expansion review" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Cumulative · Expansion" }),
    ).toBeVisible();
    expect(
      screen.getByText(/initiative choices are temporarily unavailable/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("combobox", {
        name: "Choose an existing initiative",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm grouping" }),
    ).not.toBeInTheDocument();
  });

  it("contains a malformed initiative directory without hiding validated memory", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory"))
        return jsonResponse(memory(true));
      if (url.endsWith("/conversation-threads"))
        return jsonResponse([{ id: "thread-without-required-fields" }]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByRole("link", { name: "January expansion discovery" }),
    ).toBeVisible();
    expect(
      screen.getByText(/initiative choices are temporarily unavailable/i),
    ).toBeVisible();
    expect(
      screen.queryByText(/unexpected initiative directory response/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reload memory" }),
    ).not.toBeInTheDocument();
  });

  it("atomically rejects a mixed-organisation initiative directory", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory"))
        return jsonResponse(memory(true));
      if (url.endsWith("/conversation-threads")) {
        return jsonResponse([
          thread,
          {
            ...thread,
            id: "thread-private-foreign",
            organisationId: "organisation-2",
            name: "Private foreign initiative",
          },
        ]);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByRole("link", { name: "January expansion discovery" }),
    ).toBeVisible();
    expect(
      screen.getByText(/initiative choices are temporarily unavailable/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("combobox", {
        name: "Choose an existing initiative",
      }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Private foreign initiative")).toBeNull();
  });

  it("restores initiative choices after retrying the optional directory", async () => {
    let directoryAttempts = 0;
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory"))
        return jsonResponse(memory(true));
      if (url.endsWith("/conversation-threads")) {
        directoryAttempts += 1;
        return directoryAttempts === 1
          ? jsonResponse({ message: "Directory unavailable" }, 503)
          : jsonResponse([thread]);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Retry initiative choices",
      }),
    );

    const initiativeSelect = await screen.findByRole("combobox", {
      name: "Choose an existing initiative",
    });
    expect(initiativeSelect).toBeVisible();
    expect(
      within(initiativeSelect).getByRole("option", { name: /Expansion/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/initiative choices are temporarily unavailable/i),
    ).not.toBeInTheDocument();
    expect(directoryAttempts).toBe(2);
  });

  it("finishes a successful assignment without waiting for the optional directory refresh", async () => {
    let assigned = false;
    let directoryAttempts = 0;
    const directoryRefresh = createDeferred<Response>();
    vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory"))
        return jsonResponse(memory(assigned));
      if (url.endsWith("/conversation-threads") && !init?.method) {
        directoryAttempts += 1;
        return directoryAttempts === 1
          ? jsonResponse([thread])
          : directoryRefresh.promise;
      }
      if (url.endsWith("/thread-assignment") && init?.method === "PUT") {
        assigned = true;
        return jsonResponse(memory(true).assignment);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Expansion · Same company, 1 participant in common",
      }),
    );

    expect(await screen.findByText("Confirmed · Expansion")).toBeVisible();
    expect(
      screen.getByPlaceholderText("For example, APAC renewal programme"),
    ).toBeEnabled();
    expect(directoryAttempts).toBe(2);

    directoryRefresh.resolve(jsonResponse([thread]));
    expect(
      await screen.findByRole("combobox", {
        name: "Choose an existing initiative",
      }),
    ).toBeVisible();
  });

  it("preserves verified memory when a post-mutation reload has the wrong organisation", async () => {
    let memoryReads = 0;
    vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory")) {
        memoryReads += 1;
        return jsonResponse(
          memoryReads === 1
            ? memory(true)
            : { ...memory(true), organisationId: "organisation-2" },
        );
      }
      if (url.endsWith("/conversation-threads")) return jsonResponse([thread]);
      if (url.endsWith("/thread-assignment") && init?.method === "PUT") {
        return jsonResponse(memory(false).assignment);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByRole("link", { name: "March expansion review" }),
    ).toBeVisible();
    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Choose an existing initiative",
      }),
      { target: { value: "" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm grouping" }));

    expect(
      await screen.findByText(/conversation memory returned an unexpected/i),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "March expansion review" }),
    ).toBeVisible();
    expect(screen.getByText("Confirmed · Expansion")).toBeVisible();
  });

  it("keeps a required memory failure fatal even when initiative choices load", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory"))
        return new Response(null, { status: 503 });
      if (url.endsWith("/conversation-threads")) return jsonResponse([thread]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByRole("button", { name: "Reload memory" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Confirmed initiative", { selector: "p" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "March expansion review" }),
    ).not.toBeInTheDocument();
  });

  it("contains an unexpected response without replacing the surrounding conversation page", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory")) {
        return jsonResponse({ id: "interaction-shaped-response" });
      }
      if (url.endsWith("/conversation-threads")) return jsonResponse([]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <div>
        <p>Surrounding conversation remains available</p>
        <ConversationMemory
          interactionId="interaction-1"
          companyId="company-1"
        />
      </div>,
    );

    expect(
      await screen.findByText(/conversation memory returned an unexpected/i),
    ).toBeVisible();
    expect(
      screen.getByText("Surrounding conversation remains available"),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "Initiative and framework coverage",
      }),
    ).toBeVisible();
  });

  it("keeps cumulative memory empty until a suggested initiative is explicitly confirmed", async () => {
    let assigned = false;
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.endsWith("/conversation-memory"))
          return jsonResponse(memory(assigned));
        if (url.endsWith("/conversation-threads") && !init?.method)
          return jsonResponse([thread]);
        if (url.endsWith("/thread-assignment") && init?.method === "PUT") {
          expect(JSON.parse(String(init.body))).toEqual({
            threadId: thread.id,
            expectedLockVersion: 0,
          });
          assigned = true;
          return jsonResponse(memory(true).assignment);
        }
        throw new Error(`Unexpected request: ${url}`);
      });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(await screen.findByText("Not grouped")).toBeVisible();
    expect(
      (await screen.findAllByText(/will not use a company-wide fallback/i))
        .length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("heading", {
        name: "Earlier conversations in this initiative",
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("list", {
        name: "Earlier conversations in this initiative",
      }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Timing"));
    expect(screen.getByText("April expansion follow-up")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "April expansion follow-up" }),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Expansion · Same company, 1 participant in common",
      }),
    );

    await waitFor(() =>
      expect(screen.getByText("Confirmed · Expansion")).toBeVisible(),
    );
    expect(
      screen.getByRole("heading", { name: "Cumulative · Expansion" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalled();
  });

  it("creates a separate initiative only from an explicit user action", async () => {
    let assigned = false;
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.endsWith("/conversation-memory"))
          return jsonResponse(memory(assigned));
        if (url.endsWith("/conversation-threads") && !init?.method)
          return jsonResponse(assigned ? [thread] : []);
        if (url.endsWith("/conversation-threads") && init?.method === "POST") {
          expect(JSON.parse(String(init.body))).toEqual({
            name: "Procurement pilot",
            companyId: "company-1",
            initialInteractionId: "interaction-1",
            expectedAssignmentLockVersion: 0,
          });
          assigned = true;
          return jsonResponse({ ...thread, name: "Procurement pilot" }, 201);
        }
        throw new Error(`Unexpected request: ${url}`);
      });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );
    const input = await screen.findByPlaceholderText(
      "For example, APAC renewal programme",
    );
    fireEvent.change(input, { target: { value: "Procurement pilot" } });
    fireEvent.click(
      screen.getByRole("button", { name: "Create and confirm initiative" }),
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/conversation-threads"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("shows source-linked initiative history without a selected framework", async () => {
    const noFrameworkMemory = {
      ...memory(true),
      state: "not_configured",
      safeMessage:
        "No framework is selected. Earlier conversations in the confirmed initiative remain available.",
      definition: null,
      currentConversation: null,
      confirmedThread: null,
      confirmedInitiativeHistory: {
        ...initiativeHistory,
        total: 23,
        truncated: true,
      },
    };
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory"))
        return jsonResponse(noFrameworkMemory);
      if (url.endsWith("/conversation-threads")) return jsonResponse([thread]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    const historyList = await screen.findByRole("list", {
      name: "Earlier conversations in this initiative",
    });
    const historyLinks = within(historyList).getAllByRole("link");
    expect(historyLinks.map((link) => link.textContent)).toEqual([
      "March expansion review",
      "January expansion discovery",
    ]);
    expect(historyLinks[0]).toHaveAttribute(
      "href",
      "/conversations/interaction-march",
    );
    expect(historyLinks[1]).toHaveAttribute(
      "href",
      "/conversations/interaction-january",
    );
    expect(
      screen.getByText(
        /showing the 2 most recent of 23 earlier conversations/i,
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "This conversation" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /Cumulative/ }),
    ).not.toBeInTheDocument();
  });

  it("shows the assigned-empty state without falling back to company history", async () => {
    const assignedEmpty = {
      ...memory(true),
      confirmedInitiativeHistory: {
        items: [],
        total: 0,
        truncated: false,
      },
    };
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory"))
        return jsonResponse(assignedEmpty);
      if (url.endsWith("/conversation-threads")) return jsonResponse([thread]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByText(
        /no earlier conversations are available in this confirmed initiative/i,
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("list", {
        name: "Earlier conversations in this initiative",
      }),
    ).not.toBeInTheDocument();
  });

  it.each([
    [
      "an unknown interaction type",
      {
        ...initiativeHistory,
        items: [
          { ...initiativeHistory.items[0], interactionType: "video_call" },
        ],
        total: 1,
      },
    ],
    [
      "an unknown lifecycle status",
      {
        ...initiativeHistory,
        items: [{ ...initiativeHistory.items[0], lifecycleStatus: "recorded" }],
        total: 1,
      },
    ],
    [
      "a timestamp without time or timezone",
      {
        ...initiativeHistory,
        items: [{ ...initiativeHistory.items[0], occurredAt: "2026-03-18" }],
        total: 1,
      },
    ],
    [
      "inconsistent total and truncation metadata",
      { ...initiativeHistory, total: 3, truncated: false },
    ],
  ])("fails closed when initiative history contains %s", async (_, history) => {
    const malformed = {
      ...memory(true),
      confirmedInitiativeHistory: history,
    };
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/conversation-memory")) return jsonResponse(malformed);
      if (url.endsWith("/conversation-threads")) return jsonResponse([thread]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ConversationMemory
        interactionId="interaction-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByText(/conversation memory returned an unexpected/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "March expansion review" }),
    ).not.toBeInTheDocument();
  });
});
