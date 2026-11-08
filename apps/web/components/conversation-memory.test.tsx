import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationMemory } from "@/components/conversation-memory";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
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
    generatedAt: "2026-10-31T00:00:00Z",
  };
}

afterEach(() => vi.restoreAllMocks());

describe("ConversationMemory", () => {
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
      await screen.findByText(/will not use a company-wide fallback/i),
    ).toBeVisible();
    fireEvent.click(screen.getByText("Timing"));
    expect(screen.getByText("April expansion follow-up")).toBeVisible();
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
});
