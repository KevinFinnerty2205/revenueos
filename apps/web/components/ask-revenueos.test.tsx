import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AskAnswer, AskCapabilities } from "@revenueos/shared";
import { AskRevenueOS } from "@/components/ask-revenueos";

const organisationId = "organisation-1";
const clientRequestId = "11111111-1111-4111-8111-111111111111";

vi.mock("@/components/verified-organisation-context", () => ({
  useVerifiedOrganisation: () => ({
    status: "available",
    organisationId,
  }),
}));

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

const capabilities: AskCapabilities = {
  enabled: true,
  scope: {
    organisationId,
    type: "opportunity",
    id: "opportunity-1",
    label: "Qantas expansion",
  },
  supportedScopes: ["opportunity", "account", "workspace"],
  retainedHistory: false,
  publicWebResearch: false,
  actionExecution: false,
  maxQuestionCharacters: 1000,
  maxSources: 12,
  safeMessage:
    "Ask answers from authorised Oryntela evidence. It does not search the public web or perform actions.",
};

function accountCapabilities(id: string, label: string): AskCapabilities {
  return {
    ...capabilities,
    scope: { organisationId, type: "account", id, label },
  };
}

function answer(overrides: Partial<AskAnswer> = {}): AskAnswer {
  return {
    schemaVersion: 1,
    askRequestId: "request-1",
    clientRequestId,
    answer:
      "Security review is the clearest current blocker, and the approval path is still incomplete.",
    answerStatus: "partially_supported",
    questionClass: "blocker_risk",
    summaryPoints: [
      {
        text: "The customer requires security review before pilot approval.",
        sourceIds: ["evidence-1"],
      },
    ],
    sources: [
      {
        id: "evidence-1",
        sourceType: "accepted_evidence",
        label: "Verified inbound customer email",
        occurredAt: "2026-08-23T01:00:00Z",
        excerpt: "The customer requires security review before pilot approval.",
        provenance: "customer_direct",
        href: "/opportunities/opportunity-1#customer-evidence",
      },
    ],
    uncertainties: ["The final security review date is not confirmed."],
    suggestedAction: {
      label: "Review opportunity",
      href: "/opportunities/opportunity-1",
      sourceId: "evidence-1",
    },
    followUpQuestions: ["Who is the economic buyer?"],
    scope: {
      organisationId,
      type: "opportunity",
      id: "opportunity-1",
      label: "Qantas expansion",
    },
    generatedAt: "2026-08-24T01:00:00Z",
    ...overrides,
  };
}

function accountAnswer(
  id: string,
  label: string,
  answerText: string,
): AskAnswer {
  return answer({
    answer: answerText,
    scope: { organisationId, type: "account", id, label },
    sources: [
      {
        ...answer().sources[0],
        id: `evidence-${id}`,
        label: `${label} verified note`,
        href: `/conversations/accounts/${id}`,
      },
    ],
    summaryPoints: [],
    suggestedAction: {
      label: `Review ${label}`,
      href: `/conversations/accounts/${id}`,
      sourceId: `evidence-${id}`,
    },
  });
}

describe("AskRevenueOS", () => {
  beforeEach(() => {
    vi.stubGlobal("crypto", { randomUUID: () => clientRequestId });
  });

  afterEach(() => vi.unstubAllGlobals());

  it("shows representative bounded workspace question phrasings", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...capabilities,
          scope: {
            organisationId,
            type: "workspace",
            id: null,
            label: "Your sales work",
          },
        }),
      ),
    );

    render(<AskRevenueOS scopeType="workspace" />);

    expect(
      await screen.findByRole("button", { name: "What should I ask next?" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Which commitments are overdue?" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Which commitments are overdue?" }),
    ).toBeVisible();
  });

  it("fails closed with a data-notice recovery path while keeping Search available", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            code: "data_notice_acknowledgement_required",
            message: "A data notice acknowledgement is required.",
          },
          403,
        ),
      ),
    );

    render(<AskRevenueOS scopeType="workspace" />);

    expect(
      await screen.findByText(
        "Review the data notice before using Ask Oryntela.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Review data notice" }),
    ).toHaveAttribute("href", "/onboarding");
    expect(
      screen.getByRole("link", { name: "Search records" }),
    ).toHaveAttribute("href", "/assistant?mode=search");
    expect(screen.queryByLabelText("Ask Oryntela")).not.toBeInTheDocument();
  });

  it("renders a scoped, cited answer with progressive source disclosure and follow-ups", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(capabilities))
      .mockResolvedValueOnce(jsonResponse(answer()))
      .mockResolvedValueOnce(
        jsonResponse(
          answer({
            answer: "The economic buyer is not reliably identified.",
            questionClass: "stakeholder",
          }),
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />);

    expect(await screen.findByText("About: Qantas expansion")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Ask Oryntela"), {
      target: { value: "What is holding this deal back?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(
      await screen.findByRole("heading", { name: "Partially supported" }),
    ).toBeVisible();
    expect(screen.getByText(/Security review is the clearest/)).toBeVisible();
    expect(
      screen.getByText("Answer to “What is holding this deal back?”"),
    ).toBeVisible();
    expect(screen.getByText("Why Oryntela believes it")).toBeVisible();
    expect(screen.getByText("Needs clarification")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Review opportunity" }),
    ).toHaveAttribute("href", "/opportunities/opportunity-1");

    const details = screen.getByText("Sources (1)").closest("details");
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Sources (1)"));
    expect(
      within(details as HTMLElement).getByText(
        "Verified inbound customer email",
      ),
    ).toBeVisible();
    expect(
      within(details as HTMLElement).getByText("Customer-direct"),
    ).toBeVisible();
    expect(
      within(details as HTMLElement).getByRole("link", {
        name: /Verified inbound customer email/i,
      }),
    ).toHaveAttribute("href", "/opportunities/opportunity-1#customer-evidence");

    fireEvent.click(
      screen.getByRole("button", { name: "Who is the economic buyer?" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    const followUpBody = JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body));
    expect(followUpBody).toMatchObject({
      clientRequestId,
      question: "Who is the economic buyer?",
      scopeType: "opportunity",
      scopeId: "opportunity-1",
    });
    const telemetryBody = JSON.parse(
      String(fetchMock.mock.calls[3]?.[1]?.body),
    );
    expect(telemetryBody).toEqual({
      eventType: "follow_up_selected",
      askRequestId: "request-1",
    });
  });

  it("keeps a verified answer bound to its question when a later 2xx body is invalid", async () => {
    const first = accountAnswer(
      "account-2",
      "Bayside Health",
      "Bayside confirmed the next workshop.",
    );
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(accountCapabilities("account-2", "Bayside Health")),
      )
      .mockResolvedValueOnce(jsonResponse(first))
      .mockResolvedValueOnce(
        jsonResponse({
          ...accountAnswer(
            "account-2",
            "Bayside Health",
            "This unbound answer must not be shown.",
          ),
          clientRequestId: "22222222-2222-4222-8222-222222222222",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<AskRevenueOS scopeType="account" scopeId="account-2" />);
    await screen.findByText("About: Bayside Health");
    const question = screen.getByLabelText("Ask Oryntela");
    fireEvent.change(question, { target: { value: "What changed first?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(
      await screen.findByText("Bayside confirmed the next workshop."),
    ).toBeVisible();
    expect(screen.getByText("Answer to “What changed first?”")).toBeVisible();

    fireEvent.change(question, { target: { value: "What changed second?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ask Oryntela is unavailable right now.",
    );
    expect(
      screen.getByText("Bayside confirmed the next workshop."),
    ).toBeVisible();
    expect(screen.getByText("Answer to “What changed first?”")).toBeVisible();
    expect(
      screen.queryByText("This unbound answer must not be shown."),
    ).not.toBeInTheDocument();
  });

  it("contains malformed 2xx JSON without replacing the last verified answer", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(accountCapabilities("account-2", "Bayside Health")),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          accountAnswer(
            "account-2",
            "Bayside Health",
            "Bayside confirmed the next workshop.",
          ),
        ),
      )
      .mockResolvedValueOnce(
        new Response("{", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<AskRevenueOS scopeType="account" scopeId="account-2" />);
    await screen.findByText("About: Bayside Health");
    const question = screen.getByLabelText("Ask Oryntela");
    fireEvent.change(question, { target: { value: "What changed first?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(
      await screen.findByText("Bayside confirmed the next workshop."),
    ).toBeVisible();

    fireEvent.change(question, { target: { value: "What changed second?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Oryntela couldn’t answer that right now.",
    );
    expect(
      screen.getByText("Bayside confirmed the next workshop."),
    ).toBeVisible();
    expect(screen.getByText("Answer to “What changed first?”")).toBeVisible();
  });

  it("labels Selling Profile answers as organisation context rather than customer Evidence", async () => {
    const sellingAnswer = answer({
      answer: "Sales Brain: A reviewed relationship-intelligence workspace.",
      answerStatus: "supported",
      questionClass: "selling_context",
      summaryPoints: [
        {
          text: "Sales Brain: A reviewed relationship-intelligence workspace.",
          sourceIds: ["profile-revision-2"],
        },
      ],
      sources: [
        {
          id: "profile-revision-2",
          sourceType: "selling_profile",
          label: "Approved Company & Selling Profile · revision 2",
          occurredAt: "2026-09-04T00:00:00Z",
          excerpt:
            "Sales Brain: A reviewed relationship-intelligence workspace.",
          provenance: "organisation_approved",
          href: "/settings#company-selling-profile",
        },
      ],
      uncertainties: [
        "This is organisation-approved selling context, not customer Evidence or proof about a specific buyer.",
      ],
      suggestedAction: null,
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(capabilities))
        .mockResolvedValueOnce(jsonResponse(sellingAnswer)),
    );
    render(<AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />);
    await screen.findByText("About: Qantas expansion");
    fireEvent.change(screen.getByLabelText("Ask Oryntela"), {
      target: { value: "What do we sell?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(
      await screen.findByRole("heading", {
        name: "Approved organisation context",
        level: 2,
      }),
    ).toBeVisible();
    expect(screen.getByText(/not customer Evidence/i)).toBeVisible();
    fireEvent.click(screen.getByText("Sources (1)"));
    expect(screen.getByText("Organisation-approved context")).toBeVisible();
    expect(
      screen.queryByText("Supported by current evidence"),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["conflicting", "Conflicting evidence"],
    ["unknown", "Not enough reliable evidence"],
  ] as const)(
    "renders the %s answer state without overstating confidence",
    async (status, label) => {
      const stateAnswer = answer({
        answerStatus: status,
        answer:
          status === "unknown"
            ? "I don’t have that information in Oryntela. Ask Oryntela does not research the public web yet."
            : "Oryntela found material disagreement in the current evidence.",
        summaryPoints: status === "unknown" ? [] : answer().summaryPoints,
        sources: status === "unknown" ? [] : answer().sources,
        suggestedAction: null,
      });
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValueOnce(jsonResponse(capabilities))
          .mockResolvedValueOnce(jsonResponse(stateAnswer)),
      );
      render(<AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />);
      await screen.findByText("About: Qantas expansion");
      fireEvent.click(
        screen.getByRole("button", { name: "What changed recently?" }),
      );
      expect(await screen.findByRole("heading", { name: label })).toBeVisible();
      if (status === "unknown") {
        expect(screen.queryByText(/Sources \(/)).not.toBeInTheDocument();
        expect(
          screen.getByText(/does not research the public web/i),
        ).toBeVisible();
      }
    },
  );

  it("shows loading and supports retry after a safe API error", async () => {
    let resolveAnswer: ((response: Response) => void) | undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveAnswer = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(capabilities))
      .mockReturnValueOnce(pending)
      .mockResolvedValueOnce(jsonResponse(answer()));
    vi.stubGlobal("fetch", fetchMock);
    render(<AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />);
    await screen.findByText("About: Qantas expansion");
    fireEvent.click(
      screen.getByRole("button", { name: "What is holding this deal back?" }),
    );
    expect(
      screen.getByRole("button", { name: "Checking Oryntela…" }),
    ).toBeDisabled();
    resolveAnswer?.(
      jsonResponse(
        {
          code: "ask_unavailable",
          message: "Oryntela could not answer right now.",
        },
        503,
      ),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Oryntela could not answer right now.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByText(/Security review is the clearest/),
    ).toBeVisible();
  });

  it("hides the previous answer synchronously while a new scope loads", async () => {
    const accountCapability = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse(answer()));
      }
      if (url.includes("scopeType=account")) {
        return accountCapability.promise;
      }
      return Promise.resolve(jsonResponse(capabilities));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />,
    );
    await screen.findByText("About: Qantas expansion");
    fireEvent.click(
      screen.getByRole("button", { name: "What is holding this deal back?" }),
    );
    expect(
      await screen.findByText(/Security review is the clearest/),
    ).toBeVisible();

    rerender(<AskRevenueOS scopeType="account" scopeId="account-2" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking Ask Oryntela availability",
    );
    expect(
      screen.queryByText(/Security review is the clearest/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Review opportunity" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Ask Oryntela")).not.toBeInTheDocument();

    await act(async () => {
      accountCapability.resolve(
        jsonResponse(accountCapabilities("account-2", "Bayside Health")),
      );
      await accountCapability.promise;
    });
    expect(await screen.findByText("About: Bayside Health")).toBeVisible();
  });

  it("ignores a late answer from the previous scope", async () => {
    const opportunityAnswer = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as {
          scopeId: string | null;
        };
        return body.scopeId === "opportunity-1"
          ? opportunityAnswer.promise
          : Promise.resolve(
              jsonResponse(
                accountAnswer(
                  "account-2",
                  "Bayside Health",
                  "Bayside confirmed the next workshop.",
                ),
              ),
            );
      }
      return Promise.resolve(
        jsonResponse(
          url.includes("scopeType=account")
            ? accountCapabilities("account-2", "Bayside Health")
            : capabilities,
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />,
    );
    await screen.findByText("About: Qantas expansion");
    fireEvent.click(
      screen.getByRole("button", { name: "What is holding this deal back?" }),
    );

    rerender(<AskRevenueOS scopeType="account" scopeId="account-2" />);
    await screen.findByText("About: Bayside Health");
    fireEvent.change(screen.getByLabelText("Ask Oryntela"), {
      target: { value: "What changed for Bayside?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(
      await screen.findByText("Bayside confirmed the next workshop."),
    ).toBeVisible();

    await act(async () => {
      opportunityAnswer.resolve(jsonResponse(answer()));
      await opportunityAnswer.promise;
    });
    expect(
      screen.getByText("Bayside confirmed the next workshop."),
    ).toBeVisible();
    expect(
      screen.queryByText(/Security review is the clearest/),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("fails closed when capability or answer scope does not match", async () => {
    const mismatchedCapabilityFetch = vi
      .fn()
      .mockResolvedValue(jsonResponse(capabilities));
    vi.stubGlobal("fetch", mismatchedCapabilityFetch);
    const capabilityView = render(
      <AskRevenueOS scopeType="account" scopeId="account-2" />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ask Oryntela is unavailable right now.",
    );
    expect(
      screen.queryByText("About: Qantas expansion"),
    ).not.toBeInTheDocument();
    capabilityView.unmount();

    const answerFetch = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(accountCapabilities("account-2", "Bayside Health")),
      )
      .mockResolvedValueOnce(jsonResponse(answer()));
    vi.stubGlobal("fetch", answerFetch);
    render(<AskRevenueOS scopeType="account" scopeId="account-2" />);
    await screen.findByText("About: Bayside Health");
    fireEvent.change(screen.getByLabelText("Ask Oryntela"), {
      target: { value: "What changed for Bayside?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ask Oryntela is unavailable right now.",
    );
    expect(
      screen.queryByText(/Security review is the clearest/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Review opportunity" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("keeps the newest overlapping answer when an older request settles late", async () => {
    const firstAnswer = deferred<Response>();
    let postCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") {
          postCount += 1;
          return postCount === 1
            ? firstAnswer.promise
            : Promise.resolve(
                jsonResponse(
                  accountAnswer(
                    "account-2",
                    "Bayside Health",
                    "The newest scoped answer.",
                  ),
                ),
              );
        }
        return Promise.resolve(
          jsonResponse(accountCapabilities("account-2", "Bayside Health")),
        );
      }),
    );
    render(<AskRevenueOS scopeType="account" scopeId="account-2" />);
    await screen.findByText("About: Bayside Health");
    const question = screen.getByLabelText("Ask Oryntela");
    const form = question.closest("form");
    expect(form).not.toBeNull();
    fireEvent.change(question, { target: { value: "First question?" } });
    fireEvent.submit(form as HTMLFormElement);
    fireEvent.change(question, { target: { value: "Second question?" } });
    fireEvent.submit(form as HTMLFormElement);

    expect(await screen.findByText("The newest scoped answer.")).toBeVisible();
    await act(async () => {
      firstAnswer.resolve(
        jsonResponse(
          accountAnswer(
            "account-2",
            "Bayside Health",
            "The stale scoped answer.",
          ),
        ),
      );
      await firstAnswer.promise;
    });
    expect(screen.getByText("The newest scoped answer.")).toBeVisible();
    expect(
      screen.queryByText("The stale scoped answer."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("does not let an obsolete answer steal focus from a newer same-scope request", async () => {
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal(
      "requestAnimationFrame",
      vi.fn((callback: FrameRequestCallback) => {
        frames.push(callback);
        return frames.length;
      }),
    );
    const secondAnswer = deferred<Response>();
    let postCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") {
          postCount += 1;
          return postCount === 1
            ? Promise.resolve(
                jsonResponse(
                  accountAnswer(
                    "account-2",
                    "Bayside Health",
                    "The first scoped answer.",
                  ),
                ),
              )
            : secondAnswer.promise;
        }
        return Promise.resolve(
          jsonResponse(accountCapabilities("account-2", "Bayside Health")),
        );
      }),
    );
    render(<AskRevenueOS scopeType="account" scopeId="account-2" />);
    await screen.findByText("About: Bayside Health");
    const question = screen.getByLabelText("Ask Oryntela");
    const form = question.closest("form");
    expect(form).not.toBeNull();

    fireEvent.change(question, { target: { value: "First question?" } });
    fireEvent.submit(form as HTMLFormElement);
    const firstAnswerRegion = await screen.findByRole("region", {
      name: "Partially supported",
    });
    expect(frames).toHaveLength(1);

    fireEvent.change(question, { target: { value: "Second question?" } });
    fireEvent.submit(form as HTMLFormElement);
    question.focus();
    expect(question).toHaveFocus();

    act(() => {
      frames.shift()?.(0);
    });
    expect(question).toHaveFocus();
    expect(firstAnswerRegion).not.toHaveFocus();

    await act(async () => {
      secondAnswer.resolve(
        jsonResponse(
          accountAnswer(
            "account-2",
            "Bayside Health",
            "The second scoped answer.",
          ),
        ),
      );
      await secondAnswer.promise;
    });
    expect(await screen.findByText("The second scoped answer.")).toBeVisible();
    const secondAnswerRegion = await screen.findByRole("region", {
      name: "Partially supported",
    });
    expect(frames).toHaveLength(1);
    act(() => {
      frames.shift()?.(0);
    });
    expect(secondAnswerRegion).toHaveFocus();
  });

  it("invalidates an in-flight answer when a new submission is invalid", async () => {
    const pendingAnswer = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
        init?.method === "POST"
          ? pendingAnswer.promise
          : Promise.resolve(
              jsonResponse(accountCapabilities("account-2", "Bayside Health")),
            ),
      ),
    );
    render(<AskRevenueOS scopeType="account" scopeId="account-2" />);
    await screen.findByText("About: Bayside Health");
    const question = screen.getByLabelText("Ask Oryntela");
    const form = question.closest("form");
    expect(form).not.toBeNull();
    fireEvent.change(question, { target: { value: "A valid question?" } });
    fireEvent.submit(form as HTMLFormElement);
    fireEvent.change(question, { target: { value: "x" } });
    fireEvent.submit(form as HTMLFormElement);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a question with at least two characters.",
    );
    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();

    await act(async () => {
      pendingAnswer.resolve(
        jsonResponse(
          accountAnswer(
            "account-2",
            "Bayside Health",
            "This invalidated answer must stay hidden.",
          ),
        ),
      );
      await pendingAnswer.promise;
    });
    expect(
      screen.queryByText("This invalidated answer must stay hidden."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter a question with at least two characters.",
    );
  });
});
