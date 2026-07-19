import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FollowUpEmailContent } from "@revenueos/shared";
import {
  FollowUpEmailPanel,
  renderFollowUpEmail,
} from "@/components/follow-up-email-panel";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyFollowUpEmail = {
  state: "empty",
  generationAvailable: true,
  unavailableReason: null,
  jobId: null,
  transcriptVersion: null,
  requestedAt: null,
  startedAt: null,
  generatedAt: null,
  safeMessage: null,
  tone: null,
  followUpEmail: null,
};

const completedFollowUpEmail = {
  state: "completed",
  generationAvailable: true,
  unavailableReason: null,
  jobId: "job-1",
  transcriptVersion: 1,
  requestedAt: "2026-07-19T00:00:00Z",
  startedAt: "2026-07-19T00:00:01Z",
  generatedAt: "2026-07-19T00:00:02Z",
  safeMessage: null,
  tone: "professional",
  followUpEmail: {
    subject: "Meeting follow-up",
    greeting: "Hello,",
    summary:
      "The customer confirmed the pilot scope and implementation approach.",
    decisions: [],
    actionItems: ["Send the plan (Owner: Alex; Due: 2026-07-30)"],
    openQuestions: ["Which security reviewer will approve access?"],
    closing: "Kind regards,",
    tone: "professional",
    confidence: 0.95,
  } satisfies FollowUpEmailContent,
};

describe("FollowUpEmailPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows unavailable state until the required intelligence exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...emptyFollowUpEmail,
          generationAvailable: false,
          unavailableReason:
            "Generate Executive Summary, Decisions, Action Items and Open Questions first.",
        }),
      ),
    );

    render(<FollowUpEmailPanel meetingId="meeting-1" />);

    expect(
      await screen.findByText(
        "Generate Executive Summary, Decisions, Action Items and Open Questions first.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Unavailable")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Draft Follow-up Email" }),
    ).not.toBeInTheDocument();
  });

  it("submits exactly one selected tone and polls to completion", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(emptyFollowUpEmail))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            jobId: "job-1",
            status: "queued",
            created: true,
            transcriptVersion: 1,
            tone: "friendly",
            requestedAt: "2026-07-19T00:00:00Z",
            startedAt: null,
            completedAt: null,
          },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...emptyFollowUpEmail,
          state: "running",
          generationAvailable: false,
          jobId: "job-1",
          tone: "friendly",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...completedFollowUpEmail,
          tone: "friendly",
          followUpEmail: {
            ...completedFollowUpEmail.followUpEmail,
            tone: "friendly",
            greeting: "Hi,",
            closing: "Thanks,",
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<FollowUpEmailPanel meetingId="meeting-1" />);
    await act(async () => {
      await Promise.resolve();
    });
    const tone = screen.getByLabelText("Tone");
    fireEvent.change(tone, { target: { value: "friendly" } });
    const button = screen.getByRole("button", {
      name: "Draft Follow-up Email",
    });
    fireEvent.click(button);
    fireEvent.click(button);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
    const post = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ tone: "friendly" });

    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("Composing Follow-up Email…")).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(screen.getByText("Hi,")).toBeVisible();
    expect(screen.getByText("Thanks,")).toBeVisible();
  });

  it("copies a fully rendered plain-text email and omits empty sections", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(completedFollowUpEmail)),
    );

    render(<FollowUpEmailPanel meetingId="meeting-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Copy" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const copied = String(writeText.mock.calls[0]?.[0]);
    expect(copied).toContain("Subject: Meeting follow-up");
    expect(copied).toContain("Action Items:\n- Send the plan");
    expect(copied).toContain("Open Questions:");
    expect(copied).not.toContain("Decisions:");
    expect(copied).not.toContain("<p>");
    expect(await screen.findByText("Email copied to clipboard.")).toBeVisible();
  });

  it("regenerates with the newly selected tone", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(completedFollowUpEmail))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            jobId: "job-2",
            status: "queued",
            created: true,
            transcriptVersion: 1,
            tone: "executive",
            requestedAt: "2026-07-19T00:01:00Z",
            startedAt: null,
            completedAt: null,
          },
          202,
        ),
      )
      .mockResolvedValue(
        jsonResponse({
          ...emptyFollowUpEmail,
          state: "queued",
          generationAvailable: false,
          tone: "executive",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<FollowUpEmailPanel meetingId="meeting-1" />);
    fireEvent.change(await screen.findByLabelText("Tone"), {
      target: { value: "executive" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([, init]) =>
            init?.method === "POST" &&
            JSON.parse(String(init.body)).tone === "executive",
        ),
      ).toBe(true),
    );
  });
});

describe("renderFollowUpEmail", () => {
  it("uses plain text only", () => {
    const rendered = renderFollowUpEmail(completedFollowUpEmail.followUpEmail);
    expect(rendered).toContain("Subject: Meeting follow-up");
    expect(rendered).not.toContain("<");
  });
});
