import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyKnowledgeSources } from "@/components/company-knowledge-sources";

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("CompanyKnowledgeSources", () => {
  it("queues a website without claiming it is approved knowledge", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(
        response(
          {
            id: "source-1",
            sourceKind: "website",
            label: "Synthetic company website",
            websiteUrl: "https://example.test/",
            sourceText: null,
            characterCount: 0,
            contentFingerprint: "a".repeat(64),
            processingStatus: "queued",
            failureCode: null,
            createdByUserId: "user-1",
            createdAt: "2026-10-31T00:00:00Z",
            updatedAt: "2026-10-31T00:00:00Z",
            safeMessage:
              "This source is queued for bounded extraction. It is not used until an administrator approves it.",
          },
          201,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<CompanyKnowledgeSources />);

    await screen.findByText(
      "No company knowledge sources have been saved yet.",
    );
    fireEvent.change(screen.getByLabelText("Source label"), {
      target: { value: "Synthetic company website" },
    });
    fireEvent.change(screen.getByLabelText("Website address"), {
      target: { value: "https://example.test" },
    });
    fireEvent.click(
      screen.getByLabelText(/I confirm this is company-approved material/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save source" }));

    expect(
      (
        await screen.findAllByText(
          /not used until an administrator approves it/i,
        )
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/queued/i).length).toBeGreaterThan(0);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      sourceKind: "website",
      websiteUrl: "https://example.test",
      authorityConfirmed: true,
    });
  });

  it("reuses the same idempotency key when a response is lost and the draft is retried", async () => {
    const saved = {
      id: "source-2",
      sourceKind: "supporting_text",
      label: "Approved notes",
      websiteUrl: null,
      sourceText: "Approved conversation context.",
      characterCount: 30,
      contentFingerprint: "b".repeat(64),
      processingStatus: "ready_for_review",
      failureCode: null,
      createdByUserId: "user-1",
      createdAt: "2026-10-31T00:00:00Z",
      updatedAt: "2026-10-31T00:00:00Z",
      safeMessage: "Source text is stored for profile review.",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(
        response({ code: "temporary", message: "Try again." }, 503),
      )
      .mockResolvedValueOnce(response(saved, 201));
    vi.stubGlobal("fetch", fetchMock);
    render(<CompanyKnowledgeSources />);

    await screen.findByText(
      "No company knowledge sources have been saved yet.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Supporting text" }));
    fireEvent.change(screen.getByLabelText("Source label"), {
      target: { value: "Approved notes" },
    });
    fireEvent.change(screen.getByLabelText("Supporting text"), {
      target: { value: "Approved conversation context." },
    });
    fireEvent.click(
      screen.getByLabelText(/I confirm this is company-approved material/i),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save source" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Save source" }));
    await screen.findByText("Approved notes");

    const first = JSON.parse(String(fetchMock.mock.calls[1][1]?.body));
    const second = JSON.parse(String(fetchMock.mock.calls[2][1]?.body));
    expect(second.idempotencyKey).toBe(first.idempotencyKey);
  });
});
