import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type {
  VisualEvidence,
  VisualReviewResponse,
  VisualUploadCreateResponse,
} from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VisualEvidenceCapture } from "@/components/visual-evidence-capture";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, reject, resolve };
}

function privateImageResponse(contents: string): Response {
  return new Response(new Blob([contents], { type: "image/png" }), {
    status: 200,
    headers: { "Content-Type": "image/png" },
  });
}

function visual(overrides: Partial<VisualEvidence> = {}): VisualEvidence {
  return {
    id: "visual-1",
    interactionId: "interaction-1",
    captureSessionId: "visual-1",
    visualType: "presentation_slide",
    sourceOwnership: "unknown_origin",
    contextLabel: "Customer question board",
    filename: "board.png",
    mimeType: "image/png",
    byteSize: 68,
    width: 1,
    height: 1,
    checksumSha256: "a".repeat(64),
    capturedAt: "2026-08-14T00:00:00Z",
    processingStatus: "review",
    processingAttempts: 1,
    failureCode: null,
    providerMode: "mock",
    externalProcessing: false,
    candidates: [
      {
        id: "candidate-1",
        category: "customer_request",
        statement: "Customer asked for a security workshop.",
        originalStatement: "Customer asked for a security workshop.",
        sourceVisualId: "visual-1",
        sourceOwnership: "customer_created",
        origin: "ai_inferred",
        supportClassification: "direct",
        validationState: "unreviewed",
        reviewState: "pending",
        conflictState: "not_assessed",
        confidenceClass: "low",
        evidenceRegion: { x: 0, y: 0, width: 1, height: 1 },
        relatedEntity: null,
        extractedTextSnippet: null,
        acceptedEvidenceId: null,
        edited: false,
      },
    ],
    downloadUrl: null,
    interactionIntelligenceId: null,
    revenueBrainSnapshotId: null,
    createdAt: "2026-08-14T00:00:00Z",
    updatedAt: "2026-08-14T00:00:00Z",
    ...overrides,
  };
}

describe("VisualEvidenceCapture", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("previews before upload and requires complete review before updating intelligence", async () => {
    const pending = visual();
    const completed = visual({
      processingStatus: "completed",
      candidates: pending.candidates.map((candidate) => ({
        ...candidate,
        statement: "Customer requested a reviewed security workshop.",
        validationState: "verified",
        reviewState: "accepted",
        acceptedEvidenceId: "evidence-1",
        edited: true,
      })),
      interactionIntelligenceId: "intelligence-1",
      revenueBrainSnapshotId: "brain-1",
    });
    let saved: VisualEvidence[] = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path.endsWith("/visual-evidence") && method === "GET") {
        return Promise.resolve(jsonResponse(saved));
      }
      if (path.endsWith("/visual-evidence/uploads")) {
        return Promise.resolve(
          jsonResponse(
            {
              ...visual({ processingStatus: "uploading", candidates: [] }),
              uploadUrl:
                "/api/v1/interactions/interaction-1/visual-evidence/visual-1/content?token=signed-token",
              uploadExpiresAt: "2026-08-14T00:05:00Z",
            } satisfies VisualUploadCreateResponse,
            201,
          ),
        );
      }
      if (path.includes("/content?token=") && method === "PUT") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (path.endsWith("/complete")) {
        return Promise.resolve(
          jsonResponse(
            visual({ processingStatus: "uploaded", candidates: [] }),
          ),
        );
      }
      if (path.endsWith("/process")) {
        saved = [pending];
        return Promise.resolve(jsonResponse(pending));
      }
      if (path.endsWith("/review")) {
        saved = [completed];
        return Promise.resolve(
          jsonResponse({
            ...completed,
            acceptedCount: 1,
            rejectedCount: 0,
            interactionUpdated: true,
            revenueBrainUpdated: true,
          } satisfies VisualReviewResponse),
        );
      }
      return Promise.resolve(
        jsonResponse({ code: "not_found", message: "Unexpected request" }, 404),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", {
      randomUUID: () => "request-id",
      subtle: { digest: async () => new Uint8Array(32).buffer },
    });
    vi.stubGlobal("URL", {
      createObjectURL: () => "blob:preview",
      revokeObjectURL: vi.fn(),
    });

    render(
      <VisualEvidenceCapture
        interactionId="interaction-1"
        interactionType="presentation"
        lifecycleStatus="completed"
      />,
    );
    expect(
      screen.getByText(/never.*customer-confirmed buying signals/i),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Add customer question photo" }),
    );
    expect(screen.getByLabelText("Visual type")).toHaveValue("screenshot");
    expect(screen.getByLabelText("Who created the source?")).toHaveValue(
      "customer_created",
    );
    expect(await screen.findByText("No visual evidence added.")).toBeVisible();

    const file = new File([new Uint8Array([1, 2, 3])], "board.png", {
      type: "image/png",
      lastModified: Date.parse("2026-08-14T00:00:00Z"),
    });
    Object.defineProperty(file, "arrayBuffer", {
      value: async () => new Uint8Array([1, 2, 3]).buffer,
    });
    fireEvent.change(screen.getByLabelText("Choose an image"), {
      target: { files: [file] },
    });
    expect(screen.getByAltText("Selected visual preview")).toHaveAttribute(
      "src",
      "blob:preview",
    );
    expect(
      screen.queryByText(/Preview appears before anything is uploaded/),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Remove selected image" }),
    );
    expect(
      screen.queryByAltText("Selected visual preview"),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Choose an image"), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText("Who created the source?"), {
      target: { value: "customer_created" },
    });
    fireEvent.change(screen.getByLabelText("Context label (optional)"), {
      target: { value: "Customer question board" },
    });
    fireEvent.click(
      screen.getByLabelText(/I am authorised to upload this image/i),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Upload and prepare review" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Review suggested evidence" }),
    ).toBeVisible();
    expect(
      screen.getByText(/AI-generated · user review required/i),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Suggested statement"), {
      target: { value: "Customer requested a reviewed security workshop." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Finish review" }));
    expect(
      await screen.findByText(
        /was added to Interaction Intelligence and Revenue Brain/i,
      ),
    ).toBeVisible();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/review"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(screen.getByText("Completed")).toBeVisible();
  });

  it("shows conservative business-card and site-photo guidance with cancellation fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );
    const { rerender } = render(
      <VisualEvidenceCapture
        interactionId="interaction-1"
        interactionType="site_visit"
        lifecycleStatus="planned"
      />,
    );
    expect(
      screen.getByText(/Site photos are labelled as observed evidence/i),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Visual type"), {
      target: { value: "business_card" },
    });
    expect(screen.getByText(/Nothing is saved to People/i)).toBeVisible();

    rerender(
      <VisualEvidenceCapture
        interactionId="interaction-1"
        interactionType="site_visit"
        lifecycleStatus="cancelled"
      />,
    );
    expect(
      screen.getByText(
        /Visual capture is unavailable for a cancelled interaction/i,
      ),
    ).toBeVisible();
  });

  it("does not carry a private preview into a different visual without a download URL", async () => {
    const visualA = visual({
      id: "visual-a",
      captureSessionId: "visual-a",
      contextLabel: "Visual A preview",
      filename: "visual-a.png",
      downloadUrl: "/private/visual-a",
    });
    const visualB = visual({
      id: "visual-b",
      captureSessionId: "visual-b",
      contextLabel: "Visual B preview",
      filename: "visual-b.png",
      downloadUrl: null,
    });
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:visual-a"),
      revokeObjectURL,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.endsWith("/visual-evidence")) {
          return Promise.resolve(jsonResponse([visualA, visualB]));
        }
        if (path.endsWith("/private/visual-a")) {
          return Promise.resolve(privateImageResponse("visual-a"));
        }
        return Promise.resolve(
          jsonResponse(
            { code: "not_found", message: "Unexpected request" },
            404,
          ),
        );
      }),
    );

    render(
      <VisualEvidenceCapture
        interactionId="interaction-1"
        interactionType="presentation"
        lifecycleStatus="completed"
      />,
    );

    const reviewHeading = await screen.findByRole("heading", {
      name: "Review suggested evidence",
    });
    const review = reviewHeading.closest("section");
    expect(review).not.toBeNull();
    expect(
      await within(review as HTMLElement).findByAltText("Visual A preview"),
    ).toHaveAttribute("src", "blob:visual-a");

    const visualBCard = screen.getByText("visual-b.png").closest("li");
    expect(visualBCard).not.toBeNull();
    fireEvent.click(
      within(visualBCard as HTMLElement).getByRole("button", {
        name: "Review suggestions",
      }),
    );

    expect(
      within(review as HTMLElement).queryByAltText("Visual B preview"),
    ).not.toBeInTheDocument();
    expect(
      within(review as HTMLElement).getByText("Private preview unavailable"),
    ).toBeVisible();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:visual-a");
  });

  it("keeps the newer private preview when an obsolete request rejects", async () => {
    const visualA = visual({
      id: "visual-a",
      captureSessionId: "visual-a",
      contextLabel: "Visual A preview",
      filename: "visual-a.png",
      downloadUrl: "/private/visual-a",
    });
    const visualB = visual({
      id: "visual-b",
      captureSessionId: "visual-b",
      contextLabel: "Visual B preview",
      filename: "visual-b.png",
      downloadUrl: "/private/visual-b",
    });
    const pendingVisualA = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/visual-evidence")) {
        return Promise.resolve(jsonResponse([visualA, visualB]));
      }
      if (path.endsWith("/private/visual-a")) {
        return pendingVisualA.promise;
      }
      if (path.endsWith("/private/visual-b")) {
        return Promise.resolve(privateImageResponse("visual-b"));
      }
      return Promise.resolve(
        jsonResponse({ code: "not_found", message: "Unexpected request" }, 404),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:visual-b"),
      revokeObjectURL: vi.fn(),
    });

    render(
      <VisualEvidenceCapture
        interactionId="interaction-1"
        interactionType="presentation"
        lifecycleStatus="completed"
      />,
    );

    const reviewHeading = await screen.findByRole("heading", {
      name: "Review suggested evidence",
    });
    const review = reviewHeading.closest("section");
    expect(review).not.toBeNull();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([input]) =>
          String(input).endsWith("/private/visual-a"),
        ),
      ).toHaveLength(2),
    );

    const visualBCard = screen.getByText("visual-b.png").closest("li");
    expect(visualBCard).not.toBeNull();
    fireEvent.click(
      within(visualBCard as HTMLElement).getByRole("button", {
        name: "Review suggestions",
      }),
    );
    expect(
      await within(review as HTMLElement).findByAltText("Visual B preview"),
    ).toHaveAttribute("src", "blob:visual-b");

    await act(async () => {
      pendingVisualA.reject(new Error("obsolete private download failed"));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      within(review as HTMLElement).getByAltText("Visual B preview"),
    ).toHaveAttribute("src", "blob:visual-b");
  });
});
