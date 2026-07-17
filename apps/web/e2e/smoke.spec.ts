import { expect, test } from "@playwright/test";

test("landing page explains the current product honestly", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "The AI sales teammate that remembers every customer interaction and turns conversations into action.",
    }),
  ).toBeVisible();
  await expect(
    page.getByText(/conversation capture, AI processing/i),
  ).toBeVisible();
});

test("development user can open the protected dashboard shell", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await expect(page.getByText(/mock authentication is active/i)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Today’s Priorities" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
});

test("core entity pages remain usable at a mobile viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/companies");

  await expect(page.getByRole("heading", { name: "Companies" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Create company" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toBeVisible();
});

test("company creation exposes required validation and navigation", async ({
  page,
}) => {
  await page.goto("/companies/new");

  await expect(
    page.getByRole("heading", { name: "Create company" }),
  ).toBeVisible();
  await expect(page.getByLabel(/company name/i)).toHaveAttribute(
    "required",
    "",
  );
  await expect(page.getByRole("link", { name: "Cancel" })).toHaveAttribute(
    "href",
    "/companies",
  );
});
