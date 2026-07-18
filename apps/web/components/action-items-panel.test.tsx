import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActionItemsPanel } from "@/components/action-items-panel";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyActionItems = {
  state: "empty",
  generationAvailable: true,
  unavailableReason: null,
  jobId: null,
  transcriptVersion: null,
  requestedAt: null,
  startedAt: null,
  generatedAt: null,
  safeMessage: null,
  actionItems: null,
};

describe("ActionItemsPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows transcript unavailability without a generation control", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...emptyActionItems,
          generationAvailable: false,
          unavailableReason:
            "Add a usable transcript before generating Action Items.",
        }),
      ),
    );

    render(<ActionItemsPanel meetingId="meeting-1" />);

    expect(
      await screen.findByText(
        "Add a usable transcript before generating Action Items.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Generate Action Items" }),
    ).not.toBeInTheDocument();
  });

  it("requests generation once and prevents duplicate submissions", async () => {
    let resolvePost: ((response: Response) => void) | undefined;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(emptyActionItems))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolvePost = resolve;
          }),
      )
      .mockResolvedValue(
        jsonResponse({
          ...emptyActionItems,
          state: "queued",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ActionItemsPanel meetingId="meeting-1" />);
    const button = await screen.findByRole("button", {
      name: "Generate Action Items",
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
      await screen.findByText("Action Items generation is queued…"),
    ).toBeVisible();
  });

  it("polls without overlap, renders action items and stops at completion", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          ...emptyActionItems,
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
          actionItems: {
            actionItems: [
              {
                task: "Send the revised commercial proposal.",
                owner: "Kevin",
                dueDate: "2026-08-01",
                priority: "high",
                status: "open",
                confidence: 0.94,
                evidence:
                  "Kevin committed to send the revised proposal by 2026-08-01.",
              },
              {
                task: "Arrange the customer review.",
                owner: null,
                dueDate: null,
                priority: "medium",
                status: "open",
                confidence: 0.78,
                evidence: "The group committed to arrange a customer review.",
              },
            ],
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ActionItemsPanel meetingId="meeting-1" />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("Generating Action Items…")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });

    expect(
      screen.getByText("Send the revised commercial proposal."),
    ).toBeVisible();
    expect(screen.getByText("Kevin")).toBeVisible();
    expect(screen.getByText("1 Aug 2026")).toBeVisible();
    expect(screen.getByText("High")).toBeVisible();
    expect(screen.getAllByText("Open")).toHaveLength(2);
    expect(screen.getByText("94%")).toBeVisible();
    expect(screen.getByText("78%")).toBeVisible();
    expect(screen.getAllByText("Owner")).toHaveLength(1);
    expect(screen.getAllByText("Due date")).toHaveLength(1);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);

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
          ...emptyActionItems,
          state: "completed",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          generatedAt: "2026-07-18T00:00:02Z",
          actionItems: { actionItems: [] },
        }),
      ),
    );

    render(<ActionItemsPanel meetingId="meeting-1" />);
    expect(
      await screen.findByText(
        "No action items were identified in this meeting.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a safe failure and retries generation", async () => {
    const failed = {
      ...emptyActionItems,
      state: "failed",
      generationAvailable: true,
      jobId: "job-1",
      transcriptVersion: 1,
      safeMessage: "Action Items generation could not be completed.",
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

    render(<ActionItemsPanel meetingId="meeting-1" />);
    expect(
      await screen.findByText(
        "Action Items generation could not be completed.",
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

    const view = render(<ActionItemsPanel meetingId="meeting-1" />);
    view.unmount();
    await act(async () => {
      await Promise.resolve();
    });
    const signal = fetchMock.mock.calls[0]?.[1]?.signal;
    expect(signal?.aborted).toBe(true);
  });
});
