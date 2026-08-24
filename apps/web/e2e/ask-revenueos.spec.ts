import { expect, test, type Page } from "@playwright/test";

const opportunityId = "opportunity-qantas";
const accountId = "account-qantas";

function scope(type: "opportunity" | "account" | "workspace") {
  return type === "opportunity"
    ? { type, id: opportunityId, label: "Qantas network modernisation" }
    : type === "account"
      ? { type, id: accountId, label: "Qantas" }
      : { type, id: null, label: "Your accessible sales work" };
}

function source(
  id: string,
  label: string,
  provenance:
    "customer_direct" | "salesperson_reported" | "validated_intelligence",
  excerpt?: string,
) {
  return {
    id,
    sourceType:
      provenance === "validated_intelligence"
        ? "revenue_brain"
        : "accepted_evidence",
    label,
    occurredAt: "2026-08-23T01:00:00Z",
    excerpt:
      excerpt ??
      (provenance === "customer_direct"
        ? "The customer requires security review before pilot approval."
        : "The seller believes the review can finish this week."),
    provenance,
    href: `/opportunities/${opportunityId}#customer-evidence`,
  };
}

function askAnswer(
  question: string,
  scopeType: "opportunity" | "account" | "workspace",
) {
  const common = {
    schemaVersion: 1,
    askRequestId: `request-${question.length}`,
    suggestedAction: null,
    followUpQuestions: ["Who is the economic buyer?", "What should I do next?"],
    scope: scope(scopeType),
    generatedAt: "2026-08-24T01:00:00Z",
  };
  if (/public web|latest news|share price/iu.test(question)) {
    return {
      ...common,
      answer:
        "I don’t have that information in RevenueOS. Ask RevenueOS does not research the public web yet.",
      answerStatus: "unknown",
      questionClass: "unsupported_public_web",
      summaryPoints: [],
      sources: [],
      uncertainties: [
        "RevenueOS will not fill evidence gaps with assumptions.",
      ],
    };
  }
  if (/economic buyer/iu.test(question)) {
    return {
      ...common,
      answer:
        "The available evidence gives a partial answer. The operations lead is a champion, but the economic buyer is not reliably identified.",
      answerStatus: "partially_supported",
      questionClass: "stakeholder",
      summaryPoints: [
        {
          text: "The operations lead is the active internal champion.",
          sourceIds: ["brain-stakeholder"],
        },
      ],
      sources: [
        source(
          "brain-stakeholder",
          "Revenue Brain · Stakeholder Intelligence",
          "validated_intelligence",
          "The operations lead is the current internal champion; commercial authority remains unknown.",
        ),
      ],
      uncertainties: ["The economic buyer is not reliably identified."],
    };
  }
  if (/changed/iu.test(question)) {
    return {
      ...common,
      answer:
        "RevenueOS found material disagreement in the current evidence. The customer requires security review before approval, while seller notes say it is nearly complete.",
      answerStatus: "conflicting",
      questionClass: "recent_change",
      summaryPoints: [
        {
          text: "The customer requires security review before approval.",
          sourceIds: ["customer-security"],
        },
        {
          text: "The seller believes the review is nearly complete.",
          sourceIds: ["seller-security"],
        },
      ],
      sources: [
        source(
          "customer-security",
          "Verified inbound customer email",
          "customer_direct",
        ),
        source(
          "seller-security",
          "Seller account note",
          "salesperson_reported",
        ),
      ],
      uncertainties: ["The security state needs customer confirmation."],
    };
  }
  if (/next|today/iu.test(question)) {
    return {
      ...common,
      answer:
        "Start with the Qantas security response. It is overdue and blocks the next customer review.",
      answerStatus: "supported",
      questionClass: scopeType === "workspace" ? "daily_focus" : "action",
      summaryPoints: [
        {
          text: "Send the security response before the customer review.",
          sourceIds: ["brain-action"],
        },
      ],
      sources: [
        source(
          "brain-action",
          scopeType === "workspace"
            ? "RevenueOS Daily · 24 August 2026"
            : "Latest customer review · Next Best Action",
          "validated_intelligence",
          "The security response is overdue and blocks the next customer review.",
        ),
      ],
      uncertainties: [],
      suggestedAction: {
        label: "Review opportunity",
        href: `/opportunities/${opportunityId}`,
        sourceId: "brain-action",
      },
    };
  }
  return {
    ...common,
    answer:
      "The available evidence gives a partial answer. Security review is the clearest current blocker.",
    answerStatus: "partially_supported",
    questionClass: "blocker_risk",
    summaryPoints: [
      {
        text: "The customer requires security review before pilot approval.",
        sourceIds: ["customer-security"],
      },
      {
        text: "The seller expects the review to finish this week.",
        sourceIds: ["seller-security"],
      },
    ],
    sources: [
      source(
        "customer-security",
        "Verified inbound customer email",
        "customer_direct",
      ),
      source("seller-security", "Seller account note", "salesperson_reported"),
    ],
    uncertainties: ["The final security review date is not confirmed."],
    suggestedAction: {
      label: "Review opportunity",
      href: `/opportunities/${opportunityId}`,
      sourceId: "customer-security",
    },
  };
}

async function routeAsk(page: Page) {
  let telemetryCount = 0;
  await page.route(
    "http://localhost:8000/api/v1/ask/capabilities**",
    async (route) => {
      const url = new URL(route.request().url());
      const scopeType = (url.searchParams.get("scopeType") ?? "workspace") as
        "opportunity" | "account" | "workspace";
      await route.fulfill({
        json: {
          enabled: true,
          scope: scope(scopeType),
          supportedScopes: ["opportunity", "account", "workspace"],
          retainedHistory: false,
          publicWebResearch: false,
          actionExecution: false,
          maxQuestionCharacters: 1000,
          maxSources: 12,
          safeMessage: "Authorised RevenueOS evidence only.",
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/ask/telemetry",
    async (route) => {
      telemetryCount += 1;
      await route.fulfill({ status: 204 });
    },
  );
  await page.route("http://localhost:8000/api/v1/ask", async (route) => {
    const request = route.request().postDataJSON() as {
      question: string;
      scopeType: "opportunity" | "account" | "workspace";
    };
    await route.fulfill({
      json: askAnswer(request.question, request.scopeType),
    });
  });
  return () => telemetryCount;
}

test("Ask RevenueOS answers the flagship opportunity questions with inspectable provenance", async ({
  page,
}) => {
  const telemetryCount = await routeAsk(page);
  await page.goto(
    `/assistant?mode=ask&scope=opportunity&scopeId=${opportunityId}&question=What%20is%20holding%20this%20deal%20back%3F`,
  );

  await expect(
    page.getByText("About: Qantas network modernisation").first(),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_025B_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025b-ask-mode-desktop.png",
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Partially supported" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Security review is the clearest current blocker/i),
  ).toBeVisible();
  await expect(page.getByText("Needs clarification")).toBeVisible();
  await expect(page.getByText("Sources (2)")).toBeVisible();

  await page.getByText("Sources (2)").click();
  await expect(page.getByText("Customer-direct")).toBeVisible();
  await expect(page.getByText("Reported by salesperson")).toBeVisible();
  const sourceLink = page.getByRole("link", {
    name: /Verified inbound customer email/i,
  });
  await expect(sourceLink).toHaveAttribute(
    "href",
    `/opportunities/${opportunityId}#customer-evidence`,
  );
  await sourceLink.evaluate((element) => {
    element.addEventListener("click", (event) => event.preventDefault(), {
      once: true,
    });
    (element as HTMLElement).click();
  });
  await expect.poll(telemetryCount).toBe(1);

  if (process.env.CAPTURE_WO_025B_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025b-ask-opportunity-desktop.png",
      fullPage: true,
    });
  }

  await page
    .getByRole("button", { name: "Who is the economic buyer?" })
    .click();
  await expect(
    page.getByText(/economic buyer is not reliably identified/i).first(),
  ).toBeVisible();
  await expect.poll(telemetryCount).toBe(2);

  await page
    .getByRole("textbox", { name: "Ask RevenueOS" })
    .fill("What should I do next?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Supported by current evidence" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Start with the Qantas security response/i),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_025B_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025b-ask-opportunity-supported-desktop.png",
      fullPage: true,
    });
  }

  await page
    .getByRole("textbox", { name: "Ask RevenueOS" })
    .fill("What changed recently?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Conflicting evidence" }),
  ).toBeVisible();
  const conflictSources = page
    .locator("details")
    .filter({ hasText: "Sources (2)" });
  if ((await conflictSources.getAttribute("open")) === null) {
    await conflictSources.getByText("Sources (2)").click();
  }
  await expect(page.getByText("Customer-direct")).toBeVisible();
  await expect(page.getByText("Reported by salesperson")).toBeVisible();
  if (process.env.CAPTURE_WO_025B_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025b-ask-conflict-desktop.png",
      fullPage: true,
    });
  }

  await page
    .getByRole("textbox", { name: "Ask RevenueOS" })
    .fill("Search the public web for Qantas latest news");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Not enough reliable evidence" }),
  ).toBeVisible();
  await expect(
    page.getByText(/does not research the public web yet/i),
  ).toBeVisible();
  await expect(page.getByText(/Sources \(/iu)).toHaveCount(0);
  if (process.env.CAPTURE_WO_025B_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025b-ask-unknown-desktop.png",
      fullPage: true,
    });
  }

  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "Ask RevenueOS" }),
  ).toHaveValue("What is holding this deal back?");
  await expect(page.getByText("RevenueOS answer")).toHaveCount(0);
});

test("account conflict and workspace priority answers remain explicit on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await routeAsk(page);
  await page.goto(
    `/assistant?mode=ask&scope=account&scopeId=${accountId}&question=What%20changed%20recently%3F`,
  );
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Conflicting evidence" }),
  ).toBeVisible();
  await expect(page.getByText(/material disagreement/i)).toBeVisible();
  await expect(page.getByText("About: Qantas").first()).toBeVisible();
  await page.getByText("Sources (2)").click();
  await expect(page.getByText("Customer-direct")).toBeVisible();
  await expect(page.getByText("Reported by salesperson")).toBeVisible();
  expect(
    await page.evaluate(() => document.body.scrollWidth <= window.innerWidth),
  ).toBe(true);

  if (process.env.CAPTURE_WO_025B_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-025b-ask-account-conflict-mobile.png",
      fullPage: true,
    });
  }

  await page.goto(
    "/assistant?mode=ask&scope=workspace&question=What%20do%20I%20need%20to%20do%20today%3F",
  );
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Supported by current evidence" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Start with the Qantas security response/i),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Review opportunity" }),
  ).toHaveAttribute("href", `/opportunities/${opportunityId}`);
});
