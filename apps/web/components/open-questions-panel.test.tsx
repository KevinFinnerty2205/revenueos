import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OpenQuestionsPanel } from "@/components/open-questions-panel";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyOpenQuestions = {
  state: "empty",
  generationAvailable: true,
  unavailableReason: null,
  jobId: null,
  transcriptVersion: null,
  requestedAt: null,
  startedAt: null,
  generatedAt: null,
  safeMessage: null,
  openQuestions: null,
};

describe("OpenQuestionsPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows transcript unavailability without a generation control", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...emptyOpenQuestions,
          generationAvailable: false,
          unavailableReason:
            "Add a usable transcript before generating Open Questions.",
        }),
      ),
    );

    render(<OpenQuestionsPanel meetingId="meeting-1" />);

    expect(
      await screen.findByText(
        "Add a usable transcript before generating Open Questions.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Generate Open Questions" }),
    ).not.toBeInTheDocument();
  });

  it("requests generation once and prevents duplicate submissions", async () => {
    let resolvePost: ((response: Response) => void) | undefined;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(emptyOpenQuestions))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolvePost = resolve;
          }),
      )
      .mockResolvedValue(
        jsonResponse({
          ...emptyOpenQuestions,
          state: "queued",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<OpenQuestionsPanel meetingId="meeting-1" />);
    const button = await screen.findByRole("button", {
      name: "Generate Open Questions",
    });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(screen.getByRole("button", { name: "Requesting…" })).toBeDisabled();
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);

    await act(async () => {
      resolvePost?.(
        jsonResponse(
          {
            jobId: "job-1",
            status: "queued",
            created: true,
            transcriptVersion: 1,
            requestedAt: "2026-07-18T00:00:00Z",
            startedAt: null,
            completedAt: null,
          },
          202,
        ),
      );
    });
    expect(
      await screen.findByText("Open Questions generation is queued…"),
    ).toBeVisible();
  });

  it("polls without overlap, renders questions and stops at completion", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          ...emptyOpenQuestions,
          state: "running",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
          startedAt: "2026-07-18T00:00:01Z",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          state: "completed",
          generationAvailable: false,
          unavailableReason: null,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
          startedAt: "2026-07-18T00:00:01Z",
          generatedAt: "2026-07-18T00:00:02Z",
          safeMessage: null,
          openQuestions: {
            openQuestions: [
              {
                question: "Has legal approved the final contract terms?",
                owner: "Customer Legal",
                importance: "high",
                confidence: 0.92,
                evidence:
                  "The customer said legal approval was still outstanding.",
              },
              {
                question: "What implementation scope remains unresolved?",
                owner: null,
                importance: "medium",
                confidence: 0.84,
                evidence:
                  "The transcript did not resolve the implementation scope.",
              },
            ],
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<OpenQuestionsPanel meetingId="meeting-1" />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("Generating Open Questions…")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });

    expect(
      screen.getByText("Has legal approved the final contract terms?"),
    ).toBeVisible();
    expect(screen.getByText("Customer Legal")).toBeVisible();
    expect(screen.getByText("High")).toBeVisible();
    expect(screen.getByText("92%")).toBeVisible();
    expect(screen.getByText("84%")).toBeVisible();
    expect(screen.getAllByText("Owner")).toHaveLength(1);
    expect(screen.queryByText(/suggested answer/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/due date/i)).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("treats an empty list as a successful result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...emptyOpenQuestions,
          state: "completed",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          generatedAt: "2026-07-18T00:00:02Z",
          openQuestions: { openQuestions: [] },
        }),
      ),
    );

    render(<OpenQuestionsPanel meetingId="meeting-1" />);
    expect(
      await screen.findByText(
        "No open questions were identified in this meeting.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a safe failure, retries, and aborts an in-flight load on unmount", async () => {
    const failed = {
      ...emptyOpenQuestions,
      state: "failed",
      generationAvailable: true,
      jobId: "job-1",
      transcriptVersion: 1,
      safeMessage: "Open Questions generation could not be completed.",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(failed))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            jobId: "job-2",
            status: "queued",
            created: true,
            transcriptVersion: 1,
            requestedAt: "2026-07-18T00:00:00Z",
            startedAt: null,
            completedAt: null,
          },
          202,
        ),
      )
      .mockImplementation(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const view = render(<OpenQuestionsPanel meetingId="meeting-1" />);
    expect(
      await screen.findByText(
        "Open Questions generation could not be completed.",
      ),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Try generation again" }),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(3),
    );
    const signal = fetchMock.mock.calls.at(-1)?.[1]?.signal;
    view.unmount();
    expect(signal?.aborted).toBe(true);
  });
});
