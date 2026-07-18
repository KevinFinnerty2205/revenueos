import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionsPanel } from "@/components/decisions-panel";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyDecisions = {
  state: "empty",
  generationAvailable: true,
  unavailableReason: null,
  jobId: null,
  transcriptVersion: null,
  requestedAt: null,
  startedAt: null,
  generatedAt: null,
  safeMessage: null,
  decisions: null,
};

describe("DecisionsPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows transcript unavailability without a generation control", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...emptyDecisions,
          generationAvailable: false,
          unavailableReason:
            "Add a usable transcript before generating Decisions.",
        }),
      ),
    );

    render(<DecisionsPanel meetingId="meeting-1" />);

    expect(
      await screen.findByText(
        "Add a usable transcript before generating Decisions.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Generate Decisions" }),
    ).not.toBeInTheDocument();
  });

  it("requests generation once and prevents duplicate submissions", async () => {
    let resolvePost: ((response: Response) => void) | undefined;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(emptyDecisions))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolvePost = resolve;
          }),
      )
      .mockResolvedValue(
        jsonResponse({
          ...emptyDecisions,
          state: "queued",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DecisionsPanel meetingId="meeting-1" />);
    const button = await screen.findByRole("button", {
      name: "Generate Decisions",
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
      await screen.findByText("Decisions generation is queued…"),
    ).toBeVisible();
  });

  it("polls without overlap, renders decisions and stops at completion", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          ...emptyDecisions,
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
          decisions: {
            decisions: [
              {
                decision: "Proceed with the September pilot.",
                owner: "Jane Smith",
                status: "confirmed",
                confidence: 0.94,
                evidence:
                  "The transcript records agreement to begin in September.",
              },
              {
                decision: "Defer the pricing decision.",
                owner: null,
                status: "deferred",
                confidence: 0.78,
                evidence: "The group postponed pricing until the next meeting.",
              },
            ],
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DecisionsPanel meetingId="meeting-1" />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("Generating Decisions…")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });

    expect(screen.getByText("Proceed with the September pilot.")).toBeVisible();
    expect(screen.getByText("Jane Smith")).toBeVisible();
    expect(screen.getByText("Confirmed")).toBeVisible();
    expect(screen.getByText("94%")).toBeVisible();
    expect(screen.getByText("Deferred")).toBeVisible();
    expect(screen.getByText("78%")).toBeVisible();
    expect(screen.getAllByText("Owner")).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("treats a completed empty list as a successful no-decisions result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...emptyDecisions,
          state: "completed",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          generatedAt: "2026-07-18T00:00:02Z",
          decisions: { decisions: [] },
        }),
      ),
    );

    render(<DecisionsPanel meetingId="meeting-1" />);

    expect(
      await screen.findByText("No decisions were identified in this meeting."),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a safe failure and retries generation", async () => {
    const failed = {
      ...emptyDecisions,
      state: "failed",
      generationAvailable: true,
      jobId: "job-1",
      transcriptVersion: 1,
      safeMessage: "Decisions generation could not be completed.",
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
      .mockResolvedValue(jsonResponse({ ...failed, state: "queued" }));
    vi.stubGlobal("fetch", fetchMock);

    render(<DecisionsPanel meetingId="meeting-1" />);
    expect(
      await screen.findByText("Decisions generation could not be completed."),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Try generation again" }),
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
      ).toBe(true),
    );
  });

  it("aborts polling when unmounted", async () => {
    const fetchMock = vi.fn().mockImplementation(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const view = render(<DecisionsPanel meetingId="meeting-1" />);
    view.unmount();

    await act(async () => {
      await Promise.resolve();
    });
    const signal = fetchMock.mock.calls[0]?.[1]?.signal;
    expect(signal?.aborted).toBe(true);
  });
});
