import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationMemory } from "@/components/conversation-memory";

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

afterEach(() => vi.restoreAllMocks());

describe("ConversationMemory", () => {
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
