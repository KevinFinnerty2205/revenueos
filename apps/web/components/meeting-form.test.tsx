import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeetingForm } from "@/components/meeting-form";

const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyPage = {
  items: [],
  page: 1,
  pageSize: 100,
  total: 0,
  pages: 0,
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function meetingResponse(id: string, title: string) {
  return {
    id,
    title,
    description: null,
    meetingDate: "2026-08-01T00:00:00Z",
    meetingType: "remote",
    status: "scheduled",
    companyId: null,
  };
}

describe("MeetingForm", () => {
  afterEach(() => {
    router.push.mockReset();
    vi.unstubAllGlobals();
  });

  it("creates a meeting with a participant and supplied transcript", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: "meeting-1" }, 201));
      }
      if (url.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [{ id: "company-1", name: "Acme Australia" }],
            total: 1,
            pages: 1,
          }),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingForm />);
    expect(
      await screen.findByRole("heading", { name: "Create meeting" }),
    ).toBeVisible();

    fireEvent.change(await screen.findByLabelText(/title/i), {
      target: { value: "Acme discovery" },
    });
    fireEvent.change(screen.getByLabelText(/meeting date/i), {
      target: { value: "2026-08-01T10:00" },
    });
    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "company-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add participant" }));
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Jordan Lee" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "jordan@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Transcript text"), {
      target: { value: "Jordan confirmed the next discussion." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create meeting" }));

    await waitFor(() => expect(router.push).toHaveBeenCalled());
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/api/v1/meetings") && init?.method === "POST",
    );
    expect(createCall).toBeDefined();
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      title: "Acme discovery",
      companyId: "company-1",
      participants: [
        {
          displayName: "Jordan Lee",
          email: "jordan@example.com",
        },
      ],
      transcript: {
        rawText: "Jordan confirmed the next discussion.",
        language: "en",
        source: "manual",
      },
    });
    expect(router.push).toHaveBeenCalledWith("/meetings/meeting-1");
  });

  it("loads and updates all meeting aggregate fields", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method) {
        if (url.endsWith("/transcript")) {
          return Promise.resolve(
            jsonResponse({ id: "transcript-1", version: 2 }),
          );
        }
        return Promise.resolve(jsonResponse({ id: "meeting-1" }));
      }
      if (url.includes("/companies")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.includes("/contacts?")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.endsWith("/participants")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "participant-1",
              contactId: null,
              displayName: "Jordan Lee",
              email: "jordan@example.com",
              attendanceStatus: "invited",
              role: "attendee",
            },
          ]),
        );
      }
      if (url.endsWith("/transcript")) {
        return Promise.resolve(
          jsonResponse({
            id: "transcript-1",
            rawText: "Original text.",
            language: "en",
            version: 1,
            source: "manual",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          id: "meeting-1",
          title: "Original meeting",
          description: "Original description",
          meetingDate: "2026-08-01T00:00:00Z",
          meetingType: "remote",
          status: "scheduled",
          companyId: null,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingForm meetingId="meeting-1" />);
    expect(await screen.findByDisplayValue("Original meeting")).toBeVisible();
    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Updated meeting" },
    });
    fireEvent.change(screen.getByLabelText("Attendance"), {
      target: { value: "attended" },
    });
    fireEvent.change(screen.getByLabelText("Transcript text"), {
      target: { value: "Corrected text." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save meeting" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/meetings/meeting-1"),
    );
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/meetings/meeting-1") &&
          init?.method === "PATCH",
      ),
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/participants/participant-1") &&
          init?.method === "PATCH",
      ),
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/transcript") && init?.method === "PATCH",
      ),
    ).toBe(true);
  });

  it("hides the previous meeting while the next meeting loads and clears a missing transcript", async () => {
    const meetingB = deferred<Response>();
    const participantsB = deferred<Response>();
    const transcriptB = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "DELETE") {
        return Promise.resolve(jsonResponse({}));
      }
      if (url.includes("/companies") || url.includes("/contacts?")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.endsWith("/meetings/meeting-b/participants")) {
        return participantsB.promise;
      }
      if (url.endsWith("/meetings/meeting-b/transcript")) {
        return transcriptB.promise;
      }
      if (url.endsWith("/meetings/meeting-b")) {
        return meetingB.promise;
      }
      if (url.endsWith("/participants")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "participant-a",
              contactId: null,
              displayName: "Participant A sentinel",
              email: "a@example.com",
              attendanceStatus: "attended",
              role: "attendee",
            },
          ]),
        );
      }
      if (url.endsWith("/transcript")) {
        return Promise.resolve(
          jsonResponse({
            id: "transcript-a",
            rawText: "Transcript A sentinel",
            language: "en",
            version: 1,
            source: "manual",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse(meetingResponse("meeting-a", "Meeting A sentinel")),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );

    const { rerender } = render(<MeetingForm meetingId="meeting-a" />);
    expect(await screen.findByDisplayValue("Meeting A sentinel")).toBeVisible();
    expect(screen.getByDisplayValue("Transcript A sentinel")).toBeVisible();
    expect(screen.getByDisplayValue("Participant A sentinel")).toBeVisible();

    rerender(<MeetingForm meetingId="meeting-b" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading meeting form",
    );
    expect(
      screen.queryByDisplayValue("Meeting A sentinel"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("Transcript A sentinel"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("Participant A sentinel"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save meeting" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete meeting" }),
    ).not.toBeInTheDocument();

    await act(async () => {
      meetingB.resolve(
        jsonResponse(meetingResponse("meeting-b", "Meeting B safe")),
      );
      participantsB.resolve(jsonResponse([]));
      transcriptB.resolve(jsonResponse({}, 404));
    });

    expect(await screen.findByDisplayValue("Meeting B safe")).toBeVisible();
    expect(screen.getByLabelText("Transcript text")).toHaveValue("");
    expect(
      screen.queryByText("Participant A sentinel"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete meeting" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/meetings"));
    const deleteCalls = fetchMock.mock.calls.filter(
      ([, init]) => init?.method === "DELETE",
    );
    expect(deleteCalls).toHaveLength(1);
    expect(String(deleteCalls[0]?.[0])).toContain("/api/v1/meetings/meeting-b");
  });

  it("saves only the next meeting values and transcript version after a route transition", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method) {
        return Promise.resolve(jsonResponse({ id: "saved" }));
      }
      if (url.includes("/companies") || url.includes("/contacts?")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.endsWith("/participants")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/transcript")) {
        const isMeetingB = url.includes("meeting-b");
        return Promise.resolve(
          jsonResponse({
            id: isMeetingB ? "transcript-b" : "transcript-a",
            rawText: isMeetingB
              ? "Transcript B original"
              : "Transcript A sentinel",
            language: "en",
            version: isMeetingB ? 9 : 1,
            source: "manual",
          }),
        );
      }
      const isMeetingB = url.endsWith("/meetings/meeting-b");
      return Promise.resolve(
        jsonResponse(
          meetingResponse(
            isMeetingB ? "meeting-b" : "meeting-a",
            isMeetingB ? "Meeting B safe" : "Meeting A sentinel",
          ),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(<MeetingForm meetingId="meeting-a" />);
    expect(await screen.findByDisplayValue("Meeting A sentinel")).toBeVisible();

    rerender(<MeetingForm meetingId="meeting-b" />);
    fireEvent.change(await screen.findByDisplayValue("Meeting B safe"), {
      target: { value: "Meeting B updated" },
    });
    fireEvent.change(screen.getByLabelText("Transcript text"), {
      target: { value: "Transcript B updated" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save meeting" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/meetings/meeting-b"),
    );
    const mutationCalls = fetchMock.mock.calls.filter(([, init]) =>
      Boolean(init?.method),
    );
    expect(mutationCalls).toHaveLength(2);
    expect(
      mutationCalls.every(([url]) => String(url).includes("meeting-b")),
    ).toBe(true);
    expect(JSON.parse(String(mutationCalls[0]?.[1]?.body))).toMatchObject({
      title: "Meeting B updated",
    });
    expect(JSON.parse(String(mutationCalls[1]?.[1]?.body))).toEqual({
      rawText: "Transcript B updated",
      language: "en",
      version: 9,
    });
    expect(
      mutationCalls.some(([, init]) =>
        String(init?.body).includes("Meeting A sentinel"),
      ),
    ).toBe(false);
    expect(
      mutationCalls.some(([, init]) =>
        String(init?.body).includes("Transcript A sentinel"),
      ),
    ).toBe(false);
  });

  it("ignores a late save completion from the previous meeting session", async () => {
    const saveA = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH" && url.endsWith("/meetings/meeting-a")) {
        return saveA.promise;
      }
      if (init?.method) {
        return Promise.resolve(jsonResponse({ id: "saved" }));
      }
      if (url.includes("/companies") || url.includes("/contacts?")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.endsWith("/participants")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/transcript")) {
        return Promise.resolve(jsonResponse({}, 404));
      }
      const isMeetingB = url.endsWith("/meetings/meeting-b");
      return Promise.resolve(
        jsonResponse(
          meetingResponse(
            isMeetingB ? "meeting-b" : "meeting-a",
            isMeetingB ? "Meeting B safe" : "Meeting A sentinel",
          ),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(<MeetingForm meetingId="meeting-a" />);
    fireEvent.change(await screen.findByDisplayValue("Meeting A sentinel"), {
      target: { value: "Meeting A changed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save meeting" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            init?.method === "PATCH" &&
            String(url).endsWith("/meetings/meeting-a"),
        ),
      ).toBe(true),
    );

    await act(async () => {
      rerender(<MeetingForm meetingId="meeting-b" />);
      saveA.resolve(jsonResponse({ id: "meeting-a" }));
    });

    expect(await screen.findByDisplayValue("Meeting B safe")).toBeVisible();
    expect(screen.getByDisplayValue("Meeting B safe")).toBeVisible();
    expect(
      screen.queryByDisplayValue("Meeting A changed"),
    ).not.toBeInTheDocument();
    expect(router.push).not.toHaveBeenCalledWith("/meetings/meeting-a");
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          Boolean(init?.method) && String(url).includes("meeting-b"),
      ),
    ).toBe(false);
  });

  it("does not audit or version unchanged participants and transcript", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method) {
        return Promise.resolve(jsonResponse({ id: "meeting-1" }));
      }
      if (url.includes("/companies") || url.includes("/contacts?")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.endsWith("/participants")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "participant-1",
              contactId: null,
              displayName: "Jordan Lee",
              email: "jordan@example.com",
              attendanceStatus: "attended",
              role: "attendee",
            },
          ]),
        );
      }
      if (url.endsWith("/transcript")) {
        return Promise.resolve(
          jsonResponse({
            id: "transcript-1",
            rawText: "Original text.",
            language: "en",
            version: 1,
            source: "manual",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          id: "meeting-1",
          title: "Original meeting",
          description: null,
          meetingDate: "2026-08-01T00:00:00Z",
          meetingType: "remote",
          status: "scheduled",
          companyId: null,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingForm meetingId="meeting-1" />);
    fireEvent.change(await screen.findByDisplayValue("Original meeting"), {
      target: { value: "Updated title only" },
    });
    expect(screen.getByLabelText("Transcript text")).toHaveValue(
      "Original text.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Save meeting" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/meetings/meeting-1"),
    );
    const mutationCalls = fetchMock.mock.calls.filter(([, init]) =>
      Boolean(init?.method),
    );
    expect(
      mutationCalls.map(([url, init]) => [
        String(url).replace("http://localhost:8000", ""),
        init?.method,
      ]),
    ).toEqual([["/api/v1/meetings/meeting-1", "PATCH"]]);
  });

  it("shows participant validation without sending a mutation", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(emptyPage)));
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingForm />);
    fireEvent.change(await screen.findByLabelText(/title/i), {
      target: { value: "Discovery" },
    });
    fireEvent.change(screen.getByLabelText(/meeting date/i), {
      target: { value: "2026-08-01T10:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add participant" }));
    fireEvent.click(screen.getByRole("button", { name: "Create meeting" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Each participant needs",
    );
    expect(router.push).not.toHaveBeenCalled();
  });
});
