import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CampaignBuilder,
  CampaignDetail,
  CampaignListWorkspace,
} from "@/components/campaign-workspace";

const navigation = { push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function campaign(overrides: Record<string, unknown> = {}) {
  return {
    id: "campaign-1",
    versionId: "campaign-version-1",
    version: 1,
    name: "Australian Multi-Site CIO Outreach",
    purpose: "Book respectful introductory meetings",
    state: "ready",
    approvalMode: "review_each_send",
    ownerUserId: "user-1",
    senderUserId: "user-1",
    sourceType: "manual_contacts",
    senderTimezone: "Australia/Sydney",
    sendDays: [1, 2, 3, 4, 5],
    sendWindowStartMinutes: 510,
    sendWindowEndMinutes: 1020,
    stopOnActiveOpportunity: true,
    policyVersion: null,
    audienceCount: 2,
    eligibleCount: 1,
    blockedCount: 1,
    steps: [
      {
        id: "sequence-1",
        stepOrder: 1,
        delayDays: 0,
        objective: "introduction",
        contentStrategy: "source_backed_value",
        enabled: true,
      },
      {
        id: "sequence-2",
        stepOrder: 2,
        delayDays: 4,
        objective: "follow_up",
        contentStrategy: "truthful_follow_up",
        enabled: true,
      },
    ],
    audience: [
      {
        id: "audience-1",
        contactId: "contact-1",
        companyId: "company-1",
        recipientName: "Jane Smith",
        recipientEmail: "jane@example.test",
        recipientTrust: "provider_supplied",
        eligible: true,
        eligibilityCode: "eligible",
        eligibilityReason: "Eligible under the current organisation policy.",
      },
      {
        id: "audience-2",
        contactId: "contact-2",
        companyId: "company-2",
        recipientName: "Sam Rivera",
        recipientEmail: null,
        recipientTrust: "unknown",
        eligible: false,
        eligibilityCode: "no_business_email",
        eligibilityReason: "This Contact has no supported business email.",
      },
    ],
    metrics: {
      recipients: 0,
      active: 0,
      completed: 0,
      stopped: 0,
      blocked: 0,
      needsAttention: 0,
      messagesSent: 0,
      messagesReadyForReview: 0,
      messagesFailed: 0,
      repliesReported: 0,
      meetingsReported: 0,
    },
    canManage: true,
    canLaunch: true,
    campaignAutoSendAllowed: true,
    simulationOnly: true,
    productionMailboxAvailable: false,
    launchWarning: null,
    needsAttentionReason: null,
    launchedAt: null,
    createdAt: "2026-08-26T01:00:00Z",
    updatedAt: "2026-08-26T01:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  navigation.push.mockReset();
});

describe("Campaign workspace", () => {
  it("explains the bounded first-use workflow without bulk or vanity mechanics", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({
        items: [],
        total: 0,
        canCreate: true,
        simulationOnly: true,
        productionMailboxAvailable: false,
      }),
    );
    render(<CampaignListWorkspace />);
    expect(
      await screen.findByRole("heading", {
        name: "Start with a small, exact audience",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /CSV upload and automatic audience expansion are not supported/u,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/No production mailbox provider is enabled/u),
    ).toBeInTheDocument();
  });

  it("builds an ordered campaign from exact canonical Contact IDs", async () => {
    const captured: { body?: Record<string, unknown> } = {};
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = new URL(String(input)).pathname;
      if (path === "/api/v1/contacts") {
        return jsonResponse({
          items: [
            {
              id: "contact-1",
              organisationId: "org-1",
              companyId: "company-1",
              firstName: "Jane",
              lastName: "Smith",
              email: "jane@example.test",
              phone: null,
              jobTitle: "Chief Information Officer",
              linkedinUrl: null,
              ownerUserId: "user-1",
              createdAt: "2026-08-26T00:00:00Z",
              updatedAt: "2026-08-26T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 50,
          total: 1,
          pages: 1,
        });
      }
      if (path === "/api/v1/engage/policy") {
        return jsonResponse({
          version: 1,
          configured: true,
          outboundEnabled: true,
          providerSuppliedEmailAllowed: true,
          campaignAutoSendAllowed: true,
          cooldownHours: 72,
          maxDailySendsUser: 25,
          maxDailySendsOrg: 100,
          requireOptOutMechanism: false,
          offeringName: "Multi-site Access Management",
          valueProposition: "Consistent access operations",
          approvedCta: "Discuss next week?",
          canManage: true,
          complianceNotice: "Organisation remains responsible.",
        });
      }
      if (path === "/api/v1/engage/campaigns" && init?.method === "POST") {
        captured.body = JSON.parse(String(init.body)) as Record<
          string,
          unknown
        >;
        return jsonResponse(campaign(), 201);
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<CampaignBuilder />);
    fireEvent.click(await screen.findByLabelText(/Jane Smith/u));
    fireEvent.click(screen.getByRole("button", { name: "Review audience" }));
    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith("/campaigns/campaign-1"),
    );
    expect(captured.body).toMatchObject({
      sourceType: "manual_contacts",
      contactIds: ["contact-1"],
      approvalMode: "review_each_send",
      stopOnActiveOpportunity: true,
    });
    expect(captured.body).not.toHaveProperty("recipientEmails");
    expect(captured.body?.steps).toHaveLength(4);
  });

  it("shows exact blocked reasons and requires a second auto-send confirmation", async () => {
    let launchBody: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = new URL(String(input)).pathname;
      if (path === "/api/v1/engage/campaigns/campaign-1" && !init?.method) {
        return jsonResponse(
          campaign({ approvalMode: "approved_campaign_auto_send" }),
        );
      }
      if (path === "/api/v1/engage/campaigns/campaign-1/launch") {
        launchBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return jsonResponse(
          campaign({
            state: "active",
            canLaunch: false,
            approvalMode: "approved_campaign_auto_send",
            launchedAt: "2026-08-26T02:00:00Z",
          }),
        );
      }
      if (path === "/api/v1/engage/campaigns/campaign-1/enrollments") {
        return jsonResponse({ items: [], total: 0 });
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<CampaignDetail campaignId="campaign-1" />);
    expect(
      await screen.findAllByText(
        "This Contact has no supported business email.",
      ),
    ).toHaveLength(2);
    expect(
      screen.getByText(
        /This is not blanket approval and stops on uncertainty/u,
      ),
    ).toBeInTheDocument();
    const launch = screen.getByRole("button", {
      name: "Launch to 1 eligible Contact",
    });
    expect(launch).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/reviewed the exact audience/u));
    expect(launch).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(/explicitly authorise future validated steps/u),
    );
    fireEvent.click(launch);
    await waitFor(() =>
      expect(launchBody).toEqual({
        expectedVersion: 1,
        confirmed: true,
        autoSendConfirmed: true,
      }),
    );
  });
});
