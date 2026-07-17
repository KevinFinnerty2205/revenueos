import { expect, test } from "@playwright/test";

test("landing page explains the Sprint 1 product honestly", async ({
  page,
}) => {
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
