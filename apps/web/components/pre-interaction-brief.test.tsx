import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PreInteractionBrief } from "@/components/pre-interaction-brief";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

const emptyResponse = {
  state: "not_generated",
  generationAvailable: true,
  unavailableReason: null,
  safeMessage: null,
  brief: null,
  generatedAt: null,
  reviewed: false,
  reviewedAt: null,
  priorVersions: [],
  sourceLabels: [],
};

const completedResponse = {
  ...emptyResponse,
  state: "completed",
  generatedAt: "2026-08-14T02:00:00Z",
  sourceLabels: [
    "Interaction details",
    "Opportunity record",
    "Prior validated Meeting Intelligence",
  ],
  brief: {
    interactionId: "interaction-1",
    interactionType: "phone_call",
    briefVersion: 1,
    headline: "Confirm procurement ownership and agree the next step.",
    accountContext:
      "The opportunity is in evaluation with validated prior context.",
    recentChanges: [
      {
        change: "Procurement entered the process.",
        importance: "high",
        source: "revenue_brain",
      },
    ],
    objectives: [
      {
        objective: "Clarify procurement ownership.",
        priority: "high",
        reason: "The approval path remains unresolved.",
      },
    ],
    questionsToAsk: [
      {
        question: "Who will own the procurement process from here?",
        purpose: "Clarify the approval path.",
        priority: "high",
      },
    ],
    stakeholderFocus: [
      {
        name: "Alex Morgan",
        role: "champion",
        focus: "Confirm current priorities and the next introduction.",
      },
    ],
    openCommitments: [
      {
        commitment: "Provide the security summary.",
        owner: "Revenue team",
        dueDate: null,
      },
    ],
    risksToWatch: [
      { risk: "Security review may delay progress.", severity: "high" },
    ],
    successCriteria: ["A next step, owner and timing are agreed."],
    interactionGuidance:
      "Keep the call concise, lead with the objective and close with a confirmed next step.",
    confidence: 0.82,
  },
};

describe("PreInteractionBrief", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("generates, displays and reviews a compact phone-call brief", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (String(_input).endsWith("/review")) {
        return Promise.resolve(
          jsonResponse({
            ...completedResponse,
            reviewed: true,
            reviewedAt: "2026-08-14T02:05:00Z",
          }),
        );
      }
      if (init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({ ...completedResponse, created: true }),
        );
      }
      return Promise.resolve(jsonResponse(emptyResponse));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PreInteractionBrief
        interactionId="interaction-1"
        interactionType="phone_call"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading preparation brief",
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Prepare brief" }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Confirm procurement ownership and agree the next step.",
      }),
    ).toBeVisible();
    expect(screen.getByText("Compact call brief")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Person and role" }),
    ).toBeVisible();
    expect(screen.getByText("Alex Morgan · champion")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Purpose and desired next step" }),
    ).toBeVisible();
    expect(screen.getByText("Latest commitment")).toBeVisible();
    expect(screen.getByText("Objection or timeline issue")).toBeVisible();
    expect(screen.getByText(/Recent Revenue Brain change:/)).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Recommended questions" }),
    ).toBeVisible();
    expect(screen.getByText(/Sources: Interaction details/)).toHaveTextContent(
      "Prior validated Meeting Intelligence",
    );
    expect(screen.queryByText(/recording|prompt|provider|worker/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Mark as reviewed" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reviewed" })).toBeDisabled(),
    );
  });

  it("shows presentation-specific preparation without treating seller material as evidence", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...completedResponse,
            brief: {
              ...completedResponse.brief,
              interactionType: "presentation",
              interactionGuidance:
                "Treat seller-prepared material as context, not customer evidence, and close with a validation step.",
            },
          }),
        ),
      ),
    );

    render(
      <PreInteractionBrief
        interactionId="interaction-1"
        interactionType="presentation"
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "Presentation guidance" }),
    ).toBeVisible();
    expect(screen.getByText(/seller-prepared material/i)).toBeVisible();
  });

  it.each([
    {
      name: "not-generated",
      response: emptyResponse,
      expectedRole: "button" as const,
      expectedName: "Prepare brief",
    },
    {
      name: "completed",
      response: completedResponse,
      expectedRole: "heading" as const,
      expectedName: "Confirm procurement ownership and agree the next step.",
    },
  ])(
    "retries an ordinary load failure and recovers to $name",
    async ({ response, expectedRole, expectedName }) => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse(
            {
              code: "preparation_unavailable",
              message: "Preparation is temporarily unavailable.",
            },
            503,
          ),
        )
        .mockResolvedValueOnce(jsonResponse(response));
      vi.stubGlobal("fetch", fetchMock);

      render(
        <PreInteractionBrief
          interactionId="interaction-retry"
          interactionType="phone_call"
        />,
      );

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Preparation is temporarily unavailable.",
      );
      fireEvent.click(screen.getByRole("button", { name: "Try again" }));

      expect(screen.queryByRole("alert")).toBeNull();
      expect(screen.getByRole("status")).toHaveTextContent(
        "Loading preparation brief",
      );
      expect(
        await screen.findByRole(expectedRole, { name: expectedName }),
      ).toBeVisible();
      expect(fetchMock).toHaveBeenCalledTimes(2);
    },
  );

  it("preserves the data-notice recovery action without offering a generic retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              code: "data_notice_acknowledgement_required",
              message: "Review the data notice before preparing a brief.",
            },
            403,
          ),
        ),
      ),
    );

    render(
      <PreInteractionBrief
        interactionId="interaction-notice"
        interactionType="phone_call"
      />,
    );

    expect(
      await screen.findByRole("link", { name: "Review data notice" }),
    ).toHaveAttribute("href", "/onboarding");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("keeps failed generation on its own retry control without starting a load retry", async () => {
    let generationAttempts = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        generationAttempts += 1;
        return Promise.resolve(
          generationAttempts === 1
            ? jsonResponse(
                {
                  code: "preparation_unavailable",
                  message: "The preparation brief could not be created.",
                },
                503,
              )
            : jsonResponse({ ...completedResponse, created: true }),
        );
      }
      return Promise.resolve(jsonResponse(emptyResponse));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PreInteractionBrief
        interactionId="interaction-generation-retry"
        interactionType="phone_call"
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Prepare brief" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The preparation brief could not be created.",
    );
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Prepare brief" }));
    expect(
      await screen.findByRole("heading", {
        name: "Confirm procurement ownership and agree the next step.",
      }),
    ).toBeVisible();
    expect(generationAttempts).toBe(2);
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method !== "POST"),
    ).toHaveLength(1);
  });

  it("keeps failed review on its own retry control without overlapping a load retry", async () => {
    let reviewAttempts = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/review") && init?.method === "POST") {
        reviewAttempts += 1;
        return Promise.resolve(
          reviewAttempts === 1
            ? jsonResponse(
                {
                  code: "preparation_review_unavailable",
                  message: "The review state could not be saved.",
                },
                503,
              )
            : jsonResponse({
                ...completedResponse,
                reviewed: true,
                reviewedAt: "2026-08-14T02:05:00Z",
              }),
        );
      }
      return Promise.resolve(jsonResponse(completedResponse));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PreInteractionBrief
        interactionId="interaction-review-retry"
        interactionType="phone_call"
      />,
    );

    const review = await screen.findByRole("button", {
      name: "Mark as reviewed",
    });
    fireEvent.click(review);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The review state could not be saved.",
    );
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect(review).toBeEnabled();

    fireEvent.click(review);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reviewed" })).toBeDisabled(),
    );
    expect(reviewAttempts).toBe(2);
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method !== "POST"),
    ).toHaveLength(1);
  });

  it("ignores a stale load when the interaction changes", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      String(input).includes("interaction-first")
        ? first.promise
        : second.promise,
    );
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <PreInteractionBrief
        interactionId="interaction-first"
        interactionType="phone_call"
      />,
    );
    rerender(
      <PreInteractionBrief
        interactionId="interaction-second"
        interactionType="phone_call"
      />,
    );

    await act(async () => {
      second.resolve(jsonResponse(emptyResponse));
    });
    expect(
      await screen.findByRole("button", { name: "Prepare brief" }),
    ).toBeVisible();

    await act(async () => {
      first.resolve(jsonResponse(completedResponse));
    });
    expect(
      screen.queryByRole("heading", {
        name: "Confirm procurement ownership and agree the next step.",
      }),
    ).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("ignores a generation completion from the prior interaction during the navigation commit", async () => {
    const generation = deferred<Response>();
    const onBriefChange = vi.fn();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (
        init?.method === "POST" &&
        String(input).includes("interaction-first")
      ) {
        return generation.promise;
      }
      return Promise.resolve(jsonResponse(emptyResponse));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <PreInteractionBrief
        interactionId="interaction-first"
        interactionType="phone_call"
        onBriefChange={onBriefChange}
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Prepare brief" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    await act(async () => {
      rerender(
        <PreInteractionBrief
          interactionId="interaction-second"
          interactionType="phone_call"
          onBriefChange={onBriefChange}
        />,
      );
      generation.resolve(jsonResponse({ ...completedResponse, created: true }));
    });

    expect(
      await screen.findByRole("button", { name: "Prepare brief" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", {
        name: "Confirm procurement ownership and agree the next step.",
      }),
    ).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(onBriefChange).not.toHaveBeenCalled();
  });

  it.each([
    ["unavailable", "Link account or opportunity context"],
    ["queued", "Preparing the latest brief"],
    ["running", "Preparing the latest brief"],
    ["failed", "The brief is not ready"],
    ["cancelled", "The brief is not ready"],
  ])("renders the %s state safely", async (state, expected) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...emptyResponse,
            state,
            generationAvailable: state !== "unavailable",
            safeMessage:
              state === "failed" || state === "cancelled"
                ? "The brief is not ready. You can try again."
                : null,
          }),
        ),
      ),
    );

    render(
      <PreInteractionBrief
        interactionId={`interaction-${state}`}
        interactionType="face_to_face_meeting"
      />,
    );
    expect(await screen.findByText(new RegExp(expected, "i"))).toBeVisible();
  });
});
