import { expect, test } from "@playwright/test";

const publicPages = [
  ["/", "One sales system from prospect to handover."],
  ["/platform", "One operating system for the full sales process."],
  ["/pricing", "Choose the sales system your team needs now."],
  ["/integrations", "Keep the systems your team already relies on."],
  ["/security", "Trust comes from product behaviour, not a badge."],
  ["/contact", "Start with the conversation your team needs."],
  ["/privacy", "Oryntela Privacy Policy"],
  ["/terms", "Oryntela Terms & Conditions"],
] as const;

for (const [path, heading] of publicPages) {
  test(`${path} is a complete public Oryntela route`, async ({ page }) => {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { level: 1, name: heading }),
    ).toBeVisible();
    await expect(page.locator('meta[name="description"]')).toHaveAttribute(
      "content",
      /Oryntela/iu,
    );
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
      "href",
      new RegExp(
        path === "/" ? "oryntela\\.com\\.au/?$" : `oryntela\\.com\\.au${path}$`,
        "u",
      ),
    );
  });
}

test("marketing navigation and product visuals fit a 390px viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const menu = page.getByRole("button", { name: "Open menu" });
  await menu.focus();
  await page.keyboard.press("Enter");
  const navigation = page.getByRole("navigation", {
    name: "Mobile navigation",
  });
  await expect(navigation).toBeVisible();
  const firstLink = navigation.getByRole("link", { name: "Platform" });
  const lastLink = navigation.getByRole("link", { name: "Sign in" });
  await expect(firstLink).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(lastLink).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(firstLink).toBeFocused();
  await expect(page.locator("body")).toHaveCSS("overflow", "hidden");
  await page.keyboard.press("Escape");
  await expect(navigation).toBeHidden();
  await expect(menu).toBeFocused();
  await expect(page.locator("body")).not.toHaveCSS("overflow", "hidden");

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  const clippedPrimaryContent = await page.evaluate(() => {
    const targets = [
      document.querySelector("h1"),
      ...document.querySelectorAll("main a"),
      ...document.querySelectorAll("main img"),
    ].filter((element): element is Element => element !== null);
    return targets
      .filter((element) => {
        const bounds = element.getBoundingClientRect();
        return bounds.left < -1 || bounds.right > window.innerWidth + 1;
      })
      .map((element) => element.textContent ?? element.getAttribute("alt"));
  });
  expect(clippedPrimaryContent).toEqual([]);
  await expect(
    page.getByAltText(/Oryntela Sales Brain home showing manager deal review/i),
  ).toBeVisible();
});

test("pricing and trial facts are exact and launch-safe", async ({ page }) => {
  await page.goto("/pricing");
  await expect(page.getByText("AUD $200")).toBeVisible();
  await expect(page.getByText("AUD $2,000/year")).toBeVisible();
  await expect(page.getByText("AUD $350")).toBeVisible();
  await expect(page.getByText("AUD $3,500/year")).toBeVisible();
  await expect(page.getByText("AUD $500")).toBeVisible();
  await expect(page.getByText("AUD $5,000/year")).toBeVisible();
  await expect(page.getByText("Monthly price includes GST")).toHaveCount(3);
  await expect(
    page.getByText("Including GST · billed annually as an annual prepayment"),
  ).toHaveCount(3);
  await expect(
    page.getByText("14 days with Complete-level modules."),
  ).toBeVisible();
  await expect(page.getByText("No", { exact: true })).toHaveCount(3);
  await expect(page.getByText("Not active yet", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /checkout/i })).toHaveCount(0);
});

for (const legalPage of [
  {
    path: "/terms",
    title: "Oryntela Terms & Conditions",
    expectedSection: "20. Liability",
  },
  {
    path: "/privacy",
    title: "Oryntela Privacy Policy",
    expectedSection: "9. Retention, export and deletion",
  },
] as const) {
  test(`${legalPage.path} renders the owner-review draft accessibly at desktop and 390px`, async ({
    page,
  }) => {
    for (const viewport of [
      { width: 1_440, height: 900 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto(legalPage.path);

      await expect(
        page.getByRole("heading", { level: 1, name: legalPage.title }),
      ).toBeVisible();
      await expect(page.getByLabel("Document status")).toHaveText(
        "OWNER REVIEW DRAFT",
      );
      await expect(
        page.getByRole("heading", {
          level: 2,
          name: legalPage.expectedSection,
        }),
      ).toBeAttached();
      await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
        "content",
        /noindex, nofollow/iu,
      );

      const pageFacts = await page.locator("main").innerText();
      expect(pageFacts).toContain("Effective date: [OWNER APPROVAL DATE]");
      expect(pageFacts.match(/\[[^\]]+\]/gu)).toEqual([
        "[OWNER APPROVAL DATE]",
      ]);
      expect(pageFacts).not.toMatch(/RevenueOS/iu);
      expect(pageFacts).not.toMatch(/lawyer approved|legally reviewed/iu);

      const headingLevels = await page
        .locator("main h1, main h2, main h3")
        .evaluateAll((headings) =>
          headings.map((heading) => Number(heading.tagName.slice(1))),
        );
      expect(headingLevels[0]).toBe(1);
      for (let index = 1; index < headingLevels.length; index += 1) {
        expect(
          (headingLevels[index] ?? 0) - (headingLevels[index - 1] ?? 0),
        ).toBeLessThanOrEqual(1);
      }

      const firstSectionLink = page
        .getByRole("navigation", { name: `${legalPage.title} sections` })
        .getByRole("link")
        .first();
      await firstSectionLink.focus();
      await expect(firstSectionLink).toBeFocused();
      await page.keyboard.press("Enter");
      expect(new URL(page.url()).hash).not.toBe("");

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    }
  });
}

test("integrations are explicitly not production-active", async ({ page }) => {
  await page.goto("/integrations");
  await expect(page.getByText("Built · activation pending")).toHaveCount(4);
  await expect(page.getByText(/Not yet production-active/iu)).toHaveCount(4);
  await expect(page.getByText(/Apollo/iu)).toHaveCount(0);
});

test("contact and legal links use the approved launch-safe destinations", async ({
  page,
}) => {
  await page.goto("/contact");
  const main = page.locator("main");
  await expect(
    main.getByRole("link", { name: "Request trial access" }),
  ).toHaveAttribute(
    "href",
    "mailto:hello@oryntela.com.au?subject=Oryntela%20trial%20access%20request",
  );
  await expect(
    main.getByRole("link", { name: "Book a demo by email" }),
  ).toHaveAttribute(
    "href",
    "mailto:hello@oryntela.com.au?subject=Oryntela%20demo%20request",
  );
  await expect(
    main.getByRole("link", { name: "Contact support" }),
  ).toHaveAttribute("href", "mailto:support@oryntela.com.au");

  await page.goto("/");
  await expect(page.getByRole("link", { name: "Privacy" })).toHaveAttribute(
    "href",
    "/privacy",
  );
  await expect(page.getByRole("link", { name: "Terms" })).toHaveAttribute(
    "href",
    "/terms",
  );
});

test("robots, sitemap, OpenGraph and the safe 404 are public", async ({
  page,
  request,
}) => {
  const robotsResponse = await request.get("/robots.txt");
  expect(robotsResponse.ok()).toBe(true);
  const robotsText = await robotsResponse.text();
  expect(robotsText).toContain("Disallow: /deal-room");
  expect(robotsText).toContain("Disallow: /dashboard");
  expect(robotsText).toContain("Disallow: /sign-in");
  expect(robotsText).toContain("Sitemap: https://oryntela.com.au/sitemap.xml");

  const sitemapResponse = await request.get("/sitemap.xml");
  expect(sitemapResponse.ok()).toBe(true);
  const sitemapText = await sitemapResponse.text();
  expect(sitemapText).toContain("https://oryntela.com.au/platform");
  expect(sitemapText).not.toContain("/dashboard");
  expect(sitemapText).not.toContain("/deal-room");

  await page.goto("/");
  await expect(page.locator('meta[property="og:image"]')).toHaveCount(1);

  const response = await page.goto("/this-page-does-not-exist");
  expect(response?.status()).toBe(404);
  await expect(
    page.getByRole("heading", { name: "This page is not available" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Contact Oryntela" }),
  ).toHaveAttribute("href", "/contact");
});
