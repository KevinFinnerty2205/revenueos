import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Interaction } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OnlineMeetingCapture } from "@/components/online-meeting-capture";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const interaction: Interaction = {
  id: "interaction-online-1",
  organisationId: "organisation-1",
  companyId: "company-1",
  opportunityId: "opportunity-1",
  contactId: null,
  meetingId: "meeting-1",
  interactionType: "online_meeting",
  lifecycleStatus: "completed",
  title: "Customer discovery",
  scheduledStartAt: "2026-08-15T01:00:00Z",
  scheduledEndAt: "2026-08-15T02:00:00Z",
  actualStartAt: "2026-08-15T01:00:00Z",
  actualEndAt: "2026-08-15T02:00:00Z",
  timezone: "Australia/Sydney",
  creationOrigin: "manual",
  callDirection: null,
  callOutcome: null,
  meetingPlatform: "google_meet",
  meetingUrl: "https://meet.google.com/abc-defg-hij",
  externalMeetingId: null,
  captureSource: null,
  ingestionState: "not_started",
  durationSeconds: 3600,
  captureMethods: [],
  intelligenceState: "not_ready",
  recordingAvailable: false,
  createdByUserId: "user-1",
  briefState: "completed",
  briefGeneratedAt: "2026-08-15T00:00:00Z",
  createdAt: "2026-08-15T00:00:00Z",
  updatedAt: "2026-08-15T02:00:00Z",
};

const capabilities = {
  meetingPlatform: "google_meet",
  recordingImport: false,
  transcriptImport: true,
  nativeFetch: false,
  aiDebrief: true,
  voiceJournal: true,
  nativeConnectionState: "not_configured",
  safeMessage:
    "Authorised recording and transcript imports are available. No meeting-platform connection is configured.",
};

afterEach(() => vi.restoreAllMocks());

describe("OnlineMeetingCapture", () => {
  it("shows server capabilities and imports an authorised pasted transcript", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.endsWith("/online-meeting/capabilities")) {
          return jsonResponse(capabilities);
        }
        if (url.endsWith("/online-meeting/transcripts") && !init?.method) {
          return jsonResponse([]);
        }
        if (
          url.endsWith("/online-meeting/transcript") &&
          init?.method === "POST"
        ) {
          const payload = JSON.parse(String(init.body)) as Record<
            string,
            unknown
          >;
          expect(payload.fileName).toBe("pasted-transcript.txt");
          expect(payload.provenance).toBe("platform_generated");
          expect(payload.userAttestedAuthority).toBe(true);
          expect(payload.externalProcessingAcknowledged).toBe(true);
          return jsonResponse(
            {
              id: "import-1",
              interactionId: interaction.id,
              captureSessionId: "capture-1",
              meetingId: "meeting-1",
              transcriptVersionId: "version-1",
              transcriptId: "transcript-1",
              meetingPlatform: "google_meet",
              provenance: "platform_generated",
              sourceFormat: "txt",
              language: "en-AU",
              version: 1,
              characterCount: 24,
              timestampsPresent: false,
              speakerLabelsPresent: true,
              importedAt: "2026-08-15T03:00:00Z",
              ingestionState: "ready",
              duplicate: false,
              text: "Customer: Ready to pilot",
              segments: [],
              safeMessage: "Transcript ready.",
            },
            201,
          );
        }
        throw new Error(`Unexpected request: ${url}`);
      });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByRole("heading", { name: "Capture this meeting" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Native fetch: not configured"),
    ).toBeInTheDocument();
    expect(screen.getByText(/never joins this meeting/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Paste transcript text"), {
      target: { value: "Customer: Ready to pilot" },
    });
    const confirmations = screen.getAllByRole("checkbox");
    fireEvent.click(confirmations[0]);
    fireEvent.click(confirmations[1]);
    fireEvent.click(screen.getByRole("button", { name: "Import transcript" }));

    expect(await screen.findByText("Transcript ready")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Generate Interaction Intelligence" }),
    ).toHaveAttribute("href", "/meetings/meeting-1");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });

  it("does not present unavailable native or recording capture as working", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      return url.endsWith("/online-meeting/capabilities")
        ? jsonResponse({
            ...capabilities,
            recordingImport: false,
            transcriptImport: false,
            aiDebrief: false,
            voiceJournal: false,
            safeMessage:
              "Online-meeting import is not enabled for this workspace.",
          })
        : jsonResponse([]);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByText("Recording import: unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Transcript import: unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Import transcript" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Add Recording")).not.toBeInTheDocument();
  });

  it("reuses authorised recording import when the server enables it", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return jsonResponse({
          ...capabilities,
          recordingImport: true,
          transcriptImport: false,
          aiDebrief: false,
          voiceJournal: false,
        });
      }
      return jsonResponse([]);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByRole("heading", { name: "Add Recording" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Recording source")).toHaveValue(
      "platform_recording",
    );
    expect(screen.getByText(/does not join the meeting/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /capture meeting audio/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps debrief and Voice Journal available when no artefact import exists", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      return url.endsWith("/online-meeting/capabilities")
        ? jsonResponse({
            ...capabilities,
            recordingImport: false,
            transcriptImport: false,
            aiDebrief: true,
            voiceJournal: true,
            safeMessage: "No authorised platform artefact is available.",
          })
        : jsonResponse([]);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByRole("link", { name: "Use AI Debrief" }),
    ).toHaveAttribute("href", "#debrief");
    expect(
      screen.getByRole("link", { name: "Use Voice Journal" }),
    ).toHaveAttribute("href", "#debrief");
    expect(
      screen.queryByRole("button", { name: "Import transcript" }),
    ).not.toBeInTheDocument();
  });
});
