import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CreatePresentationReview } from "@/components/create-presentation-review";
import { CreateStudio } from "@/components/create-studio";
import { CoreNavigation } from "@/components/core-navigation";

vi.mock("next/navigation", () => ({
  usePathname: () => "/create",
}));

function jsonResponse(payload: object, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const availability = {
  moduleKey: "create",
  state: "available",
  enabled: true,
  canManage: true,
  canUploadTemplates: true,
  canCreatePresentations: true,
  message: "Create is ready for approved PowerPoint templates.",
  description: "Build reviewed presentations.",
  learnMorePath: "/create",
};

const template = {
  id: "template-1",
  name: "Approved company story",
  state: "active",
  latestVersion: {
    id: "template-version-1",
    templateId: "template-1",
    version: 1,
    processingState: "ready",
    approvalState: "approved",
    fileName: "approved.pptx",
    byteSize: 12000,
    checksumSha256: "a".repeat(64),
    slideCount: 2,
    approvedSlideCount: 2,
    requiredSlideCount: 1,
    widthEmu: 12192000,
    heightEmu: 6858000,
    warningCodes: [],
    safeFailureCode: null,
    authorityAttestationVersion: 1,
    authorityAttestedAt: "2026-08-27T00:00:00Z",
    processedAt: "2026-08-27T00:01:00Z",
    approvedAt: "2026-08-27T00:02:00Z",
    slides: [],
    contentItems: [],
    createdAt: "2026-08-27T00:00:00Z",
  },
  createdAt: "2026-08-27T00:00:00Z",
  updatedAt: "2026-08-27T00:02:00Z",
};

function presentation(
  state: "draft_plan" | "generating" | "needs_review" = "draft_plan",
) {
  return {
    id: "presentation-1",
    title: "Northstar solution overview",
    accountId: "company-1",
    accountName: "Northstar Group",
    opportunityId: "opportunity-1",
    opportunityName: "National rollout",
    objective: "solution_overview",
    audience: [
      {
        contactId: null,
        name: "Jordan Lee",
        role: "Chief Revenue Officer",
        audienceType: "executive",
      },
    ],
    focusInstruction: "Keep implementation concise.",
    templateVersionId: "template-version-1",
    templateName: "Approved company story",
    templateVersion: 1,
    state,
    reviewState: "pending",
    plan: [
      {
        id: "plan-title",
        templateSlideId: "slide-title",
        order: 1,
        title: "Approved company story",
        category: "title",
        required: true,
        modificationPolicy: "locked",
        sourceClasses: ["approved_company_content"],
        included: true,
      },
      {
        id: "plan-solution",
        templateSlideId: "slide-solution",
        order: 2,
        title: "Our solution",
        category: "solution",
        required: false,
        modificationPolicy: "text_placeholders_only",
        sourceClasses: ["approved_company_content", "customer_direct"],
        included: true,
      },
    ],
    currentVersion:
      state === "needs_review"
        ? {
            id: "version-1",
            version: 1,
            state: "needs_review",
            reviewState: "pending",
            slides: [
              {
                planItemId: "plan-solution",
                templateSlideId: "slide-solution",
                order: 1,
                title: "Our solution",
                bodyBlocks: ["Customer requested a staged implementation."],
                required: false,
                modificationPolicy: "text_placeholders_only",
                reviewState: "needs_review",
                warningCodes: ["claim_review_required"],
              },
            ],
            claims: [
              {
                id: "claim-1",
                planItemId: "plan-solution",
                blockIndex: 0,
                claim: "Customer requested a staged implementation.",
                contentType: "implementation",
                origin: "salesperson_reported",
                supportState: "reported",
                customerSafeClassification: "requires_review",
                sourceIds: ["source-1"],
                sourceLabels: ["Reported by you"],
                freshness: "current",
                paraphraseAllowed: true,
                exactTextRequired: false,
                reviewState: "pending",
              },
            ],
            warningCodes: ["review_required"],
            safeFailureCode: null,
            generatedAt: "2026-08-27T00:03:00Z",
            approvedAt: null,
            downloadAvailable: false,
            createdAt: "2026-08-27T00:02:00Z",
          }
        : null,
    createdByUserId: "user-1",
    createdAt: "2026-08-27T00:02:00Z",
    updatedAt: "2026-08-27T00:03:00Z",
  };
}

describe("RevenueOS Create", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows approved templates, presentations and the authority-gated PPTX upload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/create/availability"))
          return jsonResponse(availability);
        if (url.endsWith("/api/v1/create/templates")) {
          return jsonResponse({
            items: [template],
            canUpload: true,
            maxActiveTemplates: 20,
          });
        }
        if (url.endsWith("/api/v1/create/presentations")) {
          return jsonResponse({
            items: [presentation()],
            canCreate: true,
            maxPresentationsPerUserPerDay: 10,
            maxPresentationsPerOrganisationPerDay: 50,
          });
        }
        if (url.endsWith("/api/v1/create/business-cases")) {
          return jsonResponse({
            items: [],
            canCreate: true,
            maxActiveCasesPerAccount: 20,
          });
        }
        if (url.endsWith("/api/v1/create/value-models")) {
          return jsonResponse({
            items: [],
            canManage: true,
            maxActiveModels: 50,
          });
        }
        return jsonResponse({}, 404);
      }),
    );
    render(<CreateStudio />);

    expect(
      await screen.findByRole("heading", { name: "Sales Content Studio" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "New presentation" }),
    ).toHaveAttribute("href", "/create/presentations/new");
    expect(screen.getByText("Northstar solution overview")).toBeVisible();
    expect(screen.getByText("Approved company story")).toBeVisible();
    expect(
      screen.getByText(/authorised to upload this company content/i),
    ).toBeVisible();
    expect(screen.getByLabelText("PowerPoint template")).toHaveAttribute(
      "accept",
      expect.stringContaining(".pptx"),
    );
  });

  it("adds Create to desktop navigation without adding a fifth mobile item", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/create/availability"))
          return jsonResponse(availability);
        if (url.endsWith("/api/v1/prospect/availability"))
          return jsonResponse({ enabled: false });
        if (url.endsWith("/api/v1/engage/availability"))
          return jsonResponse({ enabled: false });
        if (url.endsWith("/api/v1/beta/capabilities"))
          return jsonResponse({ featureFlags: { engageEvents: false } });
        return jsonResponse({}, 404);
      }),
    );
    render(<CoreNavigation />);
    const desktop = screen.getByRole("navigation", { name: "Main navigation" });
    expect(
      await within(desktop).findByRole("link", { name: "Studio" }),
    ).toHaveAttribute("href", "/create");
    const mobile = screen.getByRole("navigation", {
      name: "Mobile navigation",
    });
    expect(
      within(mobile).queryByRole("link", { name: "Studio" }),
    ).not.toBeInTheDocument();
    expect(within(mobile).getAllByRole("link")).toHaveLength(4);
  });

  it("presents the plan before generation and keeps required slides fixed", async () => {
    let current = presentation();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PUT") return jsonResponse(current);
      if (init?.method === "POST" && url.endsWith("/generate")) {
        current = presentation("generating");
        return jsonResponse(current);
      }
      return jsonResponse(current);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<CreatePresentationReview presentationId="presentation-1" />);

    expect(
      await screen.findByRole("heading", {
        name: "Review the deterministic slide plan",
      }),
    ).toBeVisible();
    const requiredSlide = screen
      .getByText(/1 · Title · required/i)
      .closest("li");
    expect(requiredSlide).not.toBeNull();
    expect(
      within(requiredSlide as HTMLElement).queryByRole("button", {
        name: "Remove",
      }),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Generate from this plan" }),
    );
    expect(await screen.findByText("Rendering the PowerPoint")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/generate"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("requires an explicit decision for reported claims before approval", async () => {
    let current = presentation("needs_review");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.endsWith("/review")) {
        const version = current.currentVersion;
        if (version) version.claims[0].reviewState = "kept";
        return jsonResponse(current);
      }
      return jsonResponse(current);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<CreatePresentationReview presentationId="presentation-1" />);

    expect(
      await screen.findAllByText("Customer requested a staged implementation."),
    ).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "Approve presentation" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Keep with review" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Approve presentation" }),
      ).toBeEnabled(),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/review"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
