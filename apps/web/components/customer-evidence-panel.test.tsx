import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type {
  EmailEvidenceSource,
  OpportunitySourceEvidenceItem,
  SourceEvidenceReviewResponse,
} from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CustomerEvidencePanel } from "@/components/customer-evidence-panel";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function emailSource(): EmailEvidenceSource {
  return {
    id: "email-1",
    sourceEvidenceId: "source-evidence-1",
    companyId: "company-1",
    opportunityId: "opportunity-1",
    interactionId: null,
    sourceType: "customer_sent",
    direction: "inbound",
    senderContactId: "contact-1",
    senderIdentityState: "verified_contact",
    subjectPresent: true,
    messageAt: "2026-08-15T01:00:00Z",
    quoteHandling: "stripped",
    processingStatus: "review",
    failureCode: null,
    candidates: [
      {
        id: "candidate-1",
        category: "buying_signal",
        statement: "We are interested and ready to proceed.",
        originalStatement: "We are interested and ready to proceed.",
        sourceKind: "email",
        sourceId: "email-1",
        sourceEvidenceId: "source-evidence-1",
        sourceLabel: "Verified inbound customer email",
        sourceOrigin: "customer_sent",
        interpretationOrigin: "ai_inferred",
        originClass: "customer_direct",
        supportClass: "direct",
        sourceLocation: {
          reference: "Message paragraph 1",
          pageNumber: null,
          section: null,
          paragraphIndex: 0,
        },
        validationState: "unreviewed",
        reviewState: "pending",
        conflictState: "not_assessed",
        supersedesCandidateId: null,
        acceptedEvidenceId: null,
        edited: false,
      },
    ],
    revenueBrainSnapshotId: null,
    createdAt: "2026-08-15T01:00:00Z",
    updatedAt: "2026-08-15T01:00:00Z",
  };
}

describe("CustomerEvidencePanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requires authority and complete review before publishing customer email evidence", async () => {
    const source = emailSource();
    const accepted: OpportunitySourceEvidenceItem = {
      snapshotId: "snapshot-1",
      sourceKind: "email",
      sourceId: source.id,
      sourceType: "customer_sent",
      sourceLabel: "Verified inbound customer email",
      sourceOrigin: "customer_sent",
      occurredAt: source.messageAt,
      category: "buying_signal",
      statement: source.candidates[0].statement,
      evidenceId: "accepted-evidence-1",
      location: source.candidates[0].sourceLocation,
      originClass: "customer_direct",
      supportClass: "direct",
      conflictState: "not_assessed",
    };
    let reviewed = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path.endsWith("/api/v1/evidence/capabilities")) {
        return Promise.resolve(
          jsonResponse({
            documentEvidence: true,
            emailEvidence: true,
            supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
            emailProviderImport: false,
            documentProviderImport: false,
            safeMessage:
              "Select only evidence you are authorised to process. Gmail, Outlook and drive synchronisation are not connected.",
          }),
        );
      }
      if (path.endsWith("/api/v1/evidence/opportunities/opportunity-1")) {
        return Promise.resolve(jsonResponse(reviewed ? [accepted] : []));
      }
      if (path.includes("/api/v1/contacts?")) {
        return Promise.resolve(
          jsonResponse({
            items: [
              {
                id: "contact-1",
                organisationId: "organisation-1",
                companyId: "company-1",
                firstName: "Casey",
                lastName: "Ng",
                email: "casey@example.test",
                phone: null,
                jobTitle: "Buyer",
                linkedinUrl: null,
                ownerUserId: "user-1",
                createdAt: "2026-08-15T00:00:00Z",
                updatedAt: "2026-08-15T00:00:00Z",
              },
            ],
            page: 1,
            pageSize: 100,
            total: 1,
          }),
        );
      }
      if (path.endsWith("/api/v1/evidence/emails") && method === "POST") {
        const payload = JSON.parse(String(init?.body)) as Record<
          string,
          object
        >;
        expect(payload.sourceType).toBe("customer_sent");
        expect(payload.direction).toBe("inbound");
        expect(payload.senderContactId).toBe("contact-1");
        expect(payload.authorityConfirmed).toBe(true);
        return Promise.resolve(
          jsonResponse(
            { ...source, candidates: [], processingStatus: "received" },
            201,
          ),
        );
      }
      if (path.endsWith("/api/v1/evidence/emails/email-1/process")) {
        return Promise.resolve(jsonResponse(source));
      }
      if (path.endsWith("/api/v1/evidence/emails/email-1/review")) {
        const payload = JSON.parse(String(init?.body)) as {
          decisions: { candidateId: string; decision: string }[];
        };
        expect(payload.decisions).toEqual([
          {
            candidateId: "candidate-1",
            decision: "accept",
            statement: source.candidates[0].statement,
          },
        ]);
        reviewed = true;
        return Promise.resolve(
          jsonResponse({
            sourceKind: "email",
            sourceId: source.id,
            acceptedCount: 1,
            rejectedCount: 0,
            opportunityUpdated: true,
            revenueBrainUpdated: true,
            revenueBrainSnapshotId: "snapshot-1",
            candidates: source.candidates,
          } satisfies SourceEvidenceReviewResponse),
        );
      }
      return Promise.resolve(
        jsonResponse({ code: "not_found", message: "Unexpected request" }, 404),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "request-key" });

    render(
      <CustomerEvidencePanel
        opportunityId="opportunity-1"
        companyId="company-1"
      />,
    );
    await screen.findByText("No reviewed document or email evidence yet.");
    fireEvent.click(screen.getByRole("button", { name: "Paste email" }));
    fireEvent.change(screen.getByLabelText("Email source"), {
      target: { value: "customer_sent" },
    });
    await screen.findByRole("option", { name: "Casey Ng" });
    fireEvent.change(screen.getByLabelText("Verified customer sender"), {
      target: { value: "contact-1" },
    });
    fireEvent.change(screen.getByLabelText("Subject (optional)"), {
      target: { value: "Next steps" },
    });
    fireEvent.change(screen.getByLabelText("Plain-text email"), {
      target: { value: "We are interested and ready to proceed." },
    });
    fireEvent.click(
      screen.getByLabelText("I confirm I am authorised to use this email."),
    );
    fireEvent.click(
      screen.getByLabelText(/configured external AI service for extraction/),
    );
    fireEvent.click(screen.getByRole("button", { name: "Analyse and review" }));

    expect(
      await screen.findByRole("heading", { name: "Review every AI finding" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Finish review" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Accept all" }));
    fireEvent.change(screen.getByLabelText("Finding"), {
      target: { value: "   " },
    });
    expect(
      screen.getByRole("button", { name: "Finish review" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Finding"), {
      target: { value: source.candidates[0].statement },
    });
    expect(screen.getByRole("button", { name: "Finish review" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Finish review" }));

    expect(
      await screen.findByText(/1 finding added with source labels/),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByText("We are interested and ready to proceed."),
      ).toBeVisible(),
    );
    expect(screen.getByText(/Verified inbound customer email/)).toBeVisible();
  });

  it("honours the server evidence kill switches", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/api/v1/evidence/capabilities")) {
        return Promise.resolve(
          jsonResponse({
            documentEvidence: false,
            emailEvidence: false,
            supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
            emailProviderImport: false,
            documentProviderImport: false,
            safeMessage: "Evidence is unavailable.",
          }),
        );
      }
      if (path.endsWith("/api/v1/evidence/opportunities/opportunity-1")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(
        jsonResponse({ code: "not_found", message: "Unexpected request" }, 404),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CustomerEvidencePanel
        opportunityId="opportunity-1"
        companyId="company-1"
      />,
    );

    expect(
      await screen.findByText(
        "Document and email evidence are not enabled for this workspace.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Add document" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Paste email" }),
    ).not.toBeInTheDocument();
  });
});
