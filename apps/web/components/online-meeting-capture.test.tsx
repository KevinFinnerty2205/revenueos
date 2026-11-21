import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type {
  Interaction,
  OnlineMeetingTranscriptImport,
} from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OnlineMeetingCapture } from "@/components/online-meeting-capture";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function deferredJsonResponse(body: unknown, status = 200) {
  const jsonStarted = deferred<void>();
  const releaseJson = deferred<void>();
  const response = jsonResponse({}, status);
  vi.spyOn(response, "json").mockImplementation(async () => {
    jsonStarted.resolve();
    await releaseJson.promise;
    return body;
  });
  return { jsonStarted, releaseJson, response };
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

const secondInteraction: Interaction = {
  ...interaction,
  id: "interaction-online-2",
  meetingId: "meeting-2",
  title: "Renewal planning",
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

function transcriptImport(
  id: string,
  interactionId = interaction.id,
  version = 1,
): OnlineMeetingTranscriptImport {
  return {
    id,
    interactionId,
    captureSessionId: `capture-${id}`,
    meetingId:
      interactionId === secondInteraction.id ? "meeting-2" : "meeting-1",
    transcriptVersionId: `version-${id}`,
    transcriptId: `transcript-${id}`,
    meetingPlatform: "google_meet",
    provenance: "platform_generated",
    sourceFormat: "txt",
    language: "en-AU",
    version,
    characterCount: 24,
    timestampsPresent: false,
    speakerLabelsPresent: true,
    importedAt: "2026-08-15T03:00:00Z",
    duplicate: false,
    text: "Customer: Ready to pilot",
    segments: [],
    safeMessage: "Transcript ready.",
  };
}

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

    const onTranscriptImported = vi.fn();
    render(
      <OnlineMeetingCapture
        interaction={interaction}
        onTranscriptImported={onTranscriptImported}
      />,
    );

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
      screen.getByRole("link", { name: "Review notes and follow-up" }),
    ).toHaveAttribute(
      "href",
      "/conversations/interaction-online-1#enhanced-notes",
    );
    expect(onTranscriptImported).toHaveBeenCalledWith(
      expect.objectContaining({ meetingId: "meeting-1" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });

  it("rejects an imported transcript returned for another interaction", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
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
        return jsonResponse(
          transcriptImport("foreign-import", secondInteraction.id),
          201,
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    const onTranscriptImported = vi.fn();

    render(
      <OnlineMeetingCapture
        interaction={interaction}
        onTranscriptImported={onTranscriptImported}
      />,
    );

    const transcript = await screen.findByLabelText("Paste transcript text");
    fireEvent.change(transcript, {
      target: { value: "Private conversation A text" },
    });
    for (const checkbox of screen.getAllByRole("checkbox")) {
      fireEvent.click(checkbox);
    }
    fireEvent.click(screen.getByRole("button", { name: "Import transcript" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The transcript could not be imported. Try again.",
    );
    expect(transcript).toHaveValue("Private conversation A text");
    expect(onTranscriptImported).not.toHaveBeenCalled();
    expect(screen.queryByText("Transcript ready")).not.toBeInTheDocument();
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

  it("keeps authorised transcript import available when history is unavailable", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return jsonResponse(capabilities);
      }
      if (url.endsWith("/online-meeting/transcripts")) {
        return jsonResponse(
          { message: "private provider detail", requestId: "request-1" },
          503,
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByRole("button", { name: "Import transcript" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(
        /previous transcript import history is temporarily unavailable/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/private provider detail/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/request-1/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/authorised transcript versions? imported/i),
    ).not.toBeInTheDocument();
  });

  it("shows the import form before deferred history finishes", async () => {
    const historyRequest = deferred<Response>();
    vi.spyOn(global, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return Promise.resolve(jsonResponse(capabilities));
      }
      if (url.endsWith("/online-meeting/transcripts")) {
        return historyRequest.promise;
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByRole("button", { name: "Import transcript" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Loading previous transcript import history…"),
    ).toBeInTheDocument();

    await act(async () => {
      historyRequest.resolve(jsonResponse([]));
      await historyRequest.promise;
    });

    await waitFor(() =>
      expect(
        screen.queryByText("Loading previous transcript import history…"),
      ).not.toBeInTheDocument(),
    );
  });

  it("keeps capability failure fatal even when history succeeds", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return jsonResponse({ message: "Capture is unavailable." }, 503);
      }
      if (url.endsWith("/online-meeting/transcripts")) {
        return jsonResponse([transcriptImport("history-1")]);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Capture is unavailable.",
    );
    expect(
      screen.queryByRole("button", { name: "Import transcript" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/authorised transcript version/i),
    ).not.toBeInTheDocument();
  });

  it("shows an exact count only after history loads successfully", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return jsonResponse(capabilities);
      }
      if (url.endsWith("/online-meeting/transcripts")) {
        return jsonResponse([
          transcriptImport("history-1", interaction.id, 1),
          transcriptImport("history-2", interaction.id, 2),
        ]);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByText("2 authorised transcript versions imported."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/history is temporarily unavailable/i),
    ).not.toBeInTheDocument();
  });

  it("rejects the whole history list when one transcript belongs to another interaction", async () => {
    const foreignImport = transcriptImport(
      "foreign-history",
      secondInteraction.id,
      2,
    );
    foreignImport.text = "Private renewal negotiation from another customer";
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return jsonResponse(capabilities);
      }
      if (url.endsWith("/online-meeting/transcripts")) {
        return jsonResponse([
          transcriptImport("matching-history", interaction.id, 1),
          foreignImport,
        ]);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByText(
        /previous transcript import history is temporarily unavailable/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/authorised transcript versions? imported/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Private renewal negotiation from another customer"),
    ).not.toBeInTheDocument();

    const transcript = screen.getByLabelText("Paste transcript text");
    fireEvent.change(transcript, {
      target: { value: "Authorised current-customer transcript" },
    });
    expect(
      screen.getByRole("button", { name: "Import transcript" }),
    ).toBeEnabled();
  });

  it("does not invent a count when successful history is empty", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return jsonResponse(capabilities);
      }
      if (url.endsWith("/online-meeting/transcripts")) {
        return jsonResponse([]);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    expect(
      await screen.findByRole("button", { name: "Import transcript" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByText("Loading previous transcript import history…"),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByText(/authorised transcript versions? imported/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/history is temporarily unavailable/i),
    ).not.toBeInTheDocument();
  });

  it("shows a completed import without inventing a history total", async () => {
    const created = transcriptImport("created-1");
    vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return jsonResponse(capabilities);
      }
      if (url.endsWith("/online-meeting/transcripts")) {
        return jsonResponse({ message: "History unavailable." }, 503);
      }
      if (
        url.endsWith("/online-meeting/transcript") &&
        init?.method === "POST"
      ) {
        return jsonResponse(created, 201);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    fireEvent.change(await screen.findByLabelText("Paste transcript text"), {
      target: { value: "Customer: Ready to pilot" },
    });
    for (const checkbox of screen.getAllByRole("checkbox")) {
      fireEvent.click(checkbox);
    }
    fireEvent.click(screen.getByRole("button", { name: "Import transcript" }));

    expect(await screen.findByText("Transcript ready")).toBeInTheDocument();
    expect(
      screen.getByText(/history is temporarily unavailable/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/authorised transcript versions? imported/i),
    ).not.toBeInTheDocument();
  });

  it("merges a completed import into deferred history", async () => {
    const historyRequest = deferred<Response>();
    const created = transcriptImport("created-1", interaction.id, 2);
    vi.spyOn(global, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/online-meeting/capabilities")) {
        return Promise.resolve(jsonResponse(capabilities));
      }
      if (url.endsWith("/online-meeting/transcripts")) {
        return historyRequest.promise;
      }
      if (
        url.endsWith("/online-meeting/transcript") &&
        init?.method === "POST"
      ) {
        return Promise.resolve(jsonResponse(created, 201));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    render(<OnlineMeetingCapture interaction={interaction} />);

    fireEvent.change(await screen.findByLabelText("Paste transcript text"), {
      target: { value: "Customer: Ready to pilot" },
    });
    for (const checkbox of screen.getAllByRole("checkbox")) {
      fireEvent.click(checkbox);
    }
    fireEvent.click(screen.getByRole("button", { name: "Import transcript" }));
    expect(await screen.findByText("Transcript ready")).toBeInTheDocument();

    await act(async () => {
      historyRequest.resolve(
        jsonResponse([transcriptImport("history-1", interaction.id, 1)]),
      );
      await historyRequest.promise;
    });

    expect(
      await screen.findByText("2 authorised transcript versions imported."),
    ).toBeInTheDocument();
    expect(screen.getByText("Transcript ready")).toBeInTheDocument();
  });

  it("clears private form state and ignores delayed history on interaction change", async () => {
    const firstHistoryRequest = deferred<Response>();
    vi.spyOn(global, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (
        url.includes(`/${interaction.id}/`) &&
        url.endsWith("/capabilities")
      ) {
        return Promise.resolve(jsonResponse(capabilities));
      }
      if (url.includes(`/${interaction.id}/`) && url.endsWith("/transcripts")) {
        return firstHistoryRequest.promise;
      }
      if (
        url.includes(`/${interaction.id}/`) &&
        url.endsWith("/transcript") &&
        init?.method === "POST"
      ) {
        return Promise.resolve(
          jsonResponse(transcriptImport("first-created", interaction.id), 201),
        );
      }
      if (
        url.includes(`/${secondInteraction.id}/`) &&
        url.endsWith("/capabilities")
      ) {
        return Promise.resolve(jsonResponse(capabilities));
      }
      if (
        url.includes(`/${secondInteraction.id}/`) &&
        url.endsWith("/transcripts")
      ) {
        return Promise.resolve(
          jsonResponse([transcriptImport("second-1", secondInteraction.id)]),
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    const { rerender } = render(
      <OnlineMeetingCapture interaction={interaction} />,
    );

    fireEvent.change(await screen.findByLabelText("Paste transcript text"), {
      target: { value: "Private conversation A text" },
    });
    fireEvent.change(screen.getByLabelText("Transcript provenance"), {
      target: { value: "manually_pasted" },
    });
    for (const checkbox of screen.getAllByRole("checkbox")) {
      fireEvent.click(checkbox);
    }
    fireEvent.click(screen.getByRole("button", { name: "Import transcript" }));
    expect(await screen.findByText("Transcript ready")).toBeInTheDocument();

    rerender(<OnlineMeetingCapture interaction={secondInteraction} />);
    expect(
      screen.queryByText("Private conversation A text"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Transcript ready")).not.toBeInTheDocument();
    expect(
      await screen.findByText("1 authorised transcript version imported."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Paste transcript text")).toHaveValue("");
    expect(screen.getByLabelText("Transcript provenance")).toHaveValue(
      "platform_generated",
    );
    for (const checkbox of screen.getAllByRole("checkbox")) {
      expect(checkbox).not.toBeChecked();
    }

    const staleHistoryResponse = deferredJsonResponse([
      transcriptImport("first-1", interaction.id, 1),
      transcriptImport("first-2", interaction.id, 2),
    ]);
    firstHistoryRequest.resolve(staleHistoryResponse.response);
    await firstHistoryRequest.promise;
    await staleHistoryResponse.jsonStarted.promise;
    await act(async () => {
      staleHistoryResponse.releaseJson.resolve();
      await staleHistoryResponse.releaseJson.promise;
    });

    expect(
      screen.getByText("1 authorised transcript version imported."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("2 authorised transcript versions imported."),
    ).not.toBeInTheDocument();
  });

  it("ignores a completed POST from the previous interaction", async () => {
    const firstPostRequest = deferred<Response>();
    vi.spyOn(global, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/capabilities")) {
        return Promise.resolve(jsonResponse(capabilities));
      }
      if (url.endsWith("/transcripts")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (
        url.includes(`/${interaction.id}/`) &&
        url.endsWith("/transcript") &&
        init?.method === "POST"
      ) {
        return firstPostRequest.promise;
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    const onTranscriptImported = vi.fn();
    const { rerender } = render(
      <OnlineMeetingCapture
        interaction={interaction}
        onTranscriptImported={onTranscriptImported}
      />,
    );

    fireEvent.change(await screen.findByLabelText("Paste transcript text"), {
      target: { value: "Private conversation A text" },
    });
    for (const checkbox of screen.getAllByRole("checkbox")) {
      fireEvent.click(checkbox);
    }
    fireEvent.click(screen.getByRole("button", { name: "Import transcript" }));
    expect(screen.getByRole("button", { name: "Importing…" })).toBeDisabled();

    rerender(
      <OnlineMeetingCapture
        interaction={secondInteraction}
        onTranscriptImported={onTranscriptImported}
      />,
    );
    expect(await screen.findByLabelText("Paste transcript text")).toHaveValue(
      "",
    );

    const stalePostResponse = deferredJsonResponse(
      transcriptImport("first-created", interaction.id),
      201,
    );
    firstPostRequest.resolve(stalePostResponse.response);
    await firstPostRequest.promise;
    await stalePostResponse.jsonStarted.promise;
    await act(async () => {
      stalePostResponse.releaseJson.resolve();
      await stalePostResponse.releaseJson.promise;
    });

    await waitFor(() => expect(onTranscriptImported).not.toHaveBeenCalled());
    expect(screen.queryByText("Transcript ready")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Paste transcript text")).toHaveValue("");
  });

  it("does not bypass attestations when history is unavailable", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.endsWith("/capabilities")) {
          return jsonResponse(capabilities);
        }
        if (url.endsWith("/transcripts")) {
          return jsonResponse({ message: "History unavailable." }, 503);
        }
        if (url.endsWith("/transcript") && init?.method === "POST") {
          throw new Error("POST must not run without both attestations");
        }
        throw new Error(`Unexpected request: ${url}`);
      });

    render(<OnlineMeetingCapture interaction={interaction} />);

    fireEvent.change(await screen.findByLabelText("Paste transcript text"), {
      target: { value: "Customer: Ready to pilot" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Import transcript" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Confirm both authority and processing acknowledgements.",
    );
    expect(
      fetchMock.mock.calls.filter(
        ([input, init]) =>
          String(input).endsWith("/transcript") && init?.method === "POST",
      ),
    ).toHaveLength(0);
  });
});
