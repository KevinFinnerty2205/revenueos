import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ContactOutreachWorkspace } from "@/components/contact-outreach-workspace";

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const workspace = {
  availability: {
    moduleKey: "engage",
    state: "available",
    enabled: true,
    canManage: true,
    message: "RevenueOS Engage is available for this organisation.",
  },
  contactId: "contact-1",
  contactName: "Jane Smith",
  companyId: "company-1",
  companyName: "Northstar Facilities Group",
  jobTitle: "Chief Technology Officer",
  email: "jane.smith@northstar-facilities.example",
  emailTrust: "provider_supplied",
  permissionStatus: "assessed_by_organisation_policy",
  contactability: {
    state: "allowed",
    allowed: true,
    reason: "Allowed under the configured organisation policy.",
    trustState: "provider_supplied",
    permissionAssessedSeparately: true,
  },
  policyConfigured: true,
  productionMailboxAvailable: false,
  simulationAvailable: true,
  history: [],
};

function outreach(overrides: Record<string, unknown> = {}) {
  return {
    id: "outreach-1",
    actionId: "action-1",
    contactId: "contact-1",
    purpose: "request_meeting",
    state: "draft",
    currentVersion: 1,
    approvedVersion: null,
    version: {
      id: "version-1",
      version: 1,
      subject: "Multi-site growth at Northstar Facilities Group",
      body: "Hi Jane,\n\nNorthstar's expansion and your technology consolidation comments prompted me to get in touch.",
      senderName: "Alex Morgan",
      senderEmail: "alex@example.test",
      recipientName: "Jane Smith",
      recipientEmail: "jane.smith@northstar-facilities.example",
      recipientTrust: "provider_supplied",
      creationType: "generated",
      composerVersion: "outreach_deterministic_v1",
      personalizationUsed: true,
      sources: [
        {
          id: "source-1",
          sourceType: "prospect_observation",
          sourceId: "observation-1",
          label:
            "Northstar announced expansion into three additional Australian locations.",
          trustState: "verified",
          publisher: "Northstar Newsroom",
          publishedAt: "2026-05-14T00:00:00Z",
          url: "https://northstar-facilities.example/news/expansion",
        },
        {
          id: "source-2",
          sourceType: "approved_seller_context",
          sourceId: "org-1",
          label: "Approved seller offering",
          trustState: "approved",
          publisher: null,
          publishedAt: null,
          url: null,
        },
      ],
      warnings: [],
      createdAt: "2026-08-26T01:00:00Z",
    },
    contactability: workspace.contactability,
    relationshipWarning: null,
    execution: null,
    createdAt: "2026-08-26T01:00:00Z",
    updatedAt: "2026-08-26T01:00:00Z",
    ...overrides,
  };
}

afterEach(() => vi.restoreAllMocks());

describe("ContactOutreachWorkspace", () => {
  it("reviews source-backed copy and confirms the exact simulation preview", async () => {
    let created = false;
    let approved = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/engage/contacts/contact-1") && !init?.method) {
        return jsonResponse(workspace);
      }
      if (url.endsWith("/api/v1/engage/contacts/contact-1/outreach")) {
        created = true;
        return jsonResponse(outreach(), 201);
      }
      if (url.endsWith("/api/v1/engage/outreach/outreach-1/approve")) {
        approved = true;
        return jsonResponse(
          outreach({ state: "approved", approvedVersion: 1 }),
        );
      }
      if (url.endsWith("/api/v1/actions/action-1/execution-options")) {
        return jsonResponse({
          items: [
            {
              connectionId: "connection-1",
              connectorKey: "mock_email",
              connectorDisplayName: "Mock Email",
              capability: "send_email",
              riskClass: "external_customer_facing",
              executionMode: "simulation",
              simulationOnly: true,
            },
          ],
          total: 1,
        });
      }
      if (
        url.endsWith("/api/v1/engage/outreach/outreach-1/execution-preview")
      ) {
        return jsonResponse({
          id: "preview-1",
          actionProposalId: "action-1",
          actionVersion: 1,
          connectionId: "connection-1",
          connectorKey: "mock_email",
          connectorDisplayName: "Mock Email",
          capability: "send_email",
          riskClass: "external_customer_facing",
          executionMode: "simulation",
          simulationOnly: true,
          readiness: "ready",
          summary: "Review the email before simulation.",
          confirmationLabel: "Send email",
          previewFingerprint: "a".repeat(64),
          content: {
            kind: "email",
            senderName: "Alex Morgan",
            senderEmail: "alex@example.test",
            recipientName: "Jane Smith",
            recipient: "jane.smith@northstar-facilities.example",
            subject: "Multi-site growth at Northstar Facilities Group",
            body: "Exact approved body",
            action: "send_email",
          },
          expiresAt: "2026-08-26T01:10:00Z",
          createdAt: "2026-08-26T01:00:00Z",
        });
      }
      if (url.endsWith("/api/v1/engage/outreach/outreach-1/send")) {
        return jsonResponse(
          {
            id: "execution-1",
            actionProposalId: "action-1",
            actionVersion: 1,
            connectionId: "connection-1",
            connectorKey: "mock_email",
            connectorDisplayName: "Mock Email",
            capability: "send_email",
            riskClass: "external_customer_facing",
            executionStatus: "queued",
            executionMode: "simulation",
            simulationOnly: true,
            confirmedByUserId: "user-1",
            confirmedAt: "2026-08-26T01:00:00Z",
            startedAt: null,
            completedAt: null,
            failedAt: null,
            safeFailureCode: null,
            externalResultId: null,
            safeMessage: "The email simulation is queued.",
            attemptCount: 0,
            maxAttempts: 3,
            nextAttemptAt: null,
            canReconcile: false,
            createdAt: "2026-08-26T01:00:00Z",
            updatedAt: "2026-08-26T01:00:00Z",
          },
          202,
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ContactOutreachWorkspace contactId="contact-1" />);
    expect(
      await screen.findByRole("heading", { name: "Contact and outreach" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Provider Supplied")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Purpose"), {
      target: { value: "request_meeting" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Create outreach draft" }),
    );
    expect(await screen.findByText("Why this message?")).toBeInTheDocument();
    expect(
      screen.getByText(/three additional Australian locations/u),
    ).toBeInTheDocument();
    expect(created).toBe(true);
    expect(
      screen.getByRole("button", { name: "Save as new version" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Subject"), {
      target: { value: "Unsaved subject" },
    });
    expect(
      screen.getByRole("button", { name: "Approve current version" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/Save your changes as a new version/u),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Subject"), {
      target: { value: "Multi-site growth at Northstar Facilities Group" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Approve current version" }),
    );
    await waitFor(() => expect(approved).toBe(true));
    fireEvent.click(
      await screen.findByRole("button", { name: "Review before send" }),
    );
    expect(await screen.findByText("Simulation only")).toBeInTheDocument();
    expect(
      screen.getByText("Alex Morgan <alex@example.test>"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Jane Smith <jane.smith@northstar-facilities.example>"),
    ).toBeInTheDocument();
    expect(screen.getByText("Exact approved body")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Run email simulation" }),
    );
    expect(await screen.findByText("Queued")).toBeInTheDocument();
    expect(
      screen.getAllByText("The email simulation is queued."),
    ).not.toHaveLength(0);
  });

  it("shows a contextual not-in-plan state without a dead control", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({
        ...workspace,
        availability: {
          ...workspace.availability,
          state: "not_in_plan",
          enabled: false,
          message: "Create source-backed personalised outreach and follow-up.",
        },
        contactability: {
          ...workspace.contactability,
          state: "engage_unavailable",
          allowed: false,
          reason: "RevenueOS Engage is not enabled for this organisation.",
        },
      }),
    );
    render(<ContactOutreachWorkspace contactId="contact-1" />);
    expect(
      await screen.findByRole("heading", {
        name: "Personalised outreach is not enabled",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Review Engage settings" }),
    ).toHaveAttribute("href", "/settings");
    expect(
      screen.queryByRole("button", { name: "Create outreach draft" }),
    ).not.toBeInTheDocument();
  });

  it("reopens persisted outreach from Contact history", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/engage/contacts/contact-1")) {
        return jsonResponse({
          ...workspace,
          history: [
            {
              id: "outreach-1",
              purpose: "request_meeting",
              subject: "Persisted outreach",
              status: "draft",
              simulationOnly: false,
              createdAt: "2026-08-26T01:00:00Z",
              completedAt: null,
            },
          ],
        });
      }
      if (url.endsWith("/api/v1/engage/outreach/outreach-1")) {
        return jsonResponse(
          outreach({
            version: {
              ...outreach().version,
              subject: "Persisted outreach",
            },
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ContactOutreachWorkspace contactId="contact-1" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Persisted outreach" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Review personalised email" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Subject")).toHaveValue("Persisted outreach");
  });
});
