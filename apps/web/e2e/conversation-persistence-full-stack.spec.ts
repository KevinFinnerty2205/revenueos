import { expect, test } from "@playwright/test";
import type { DeliveryPreferenceResponse } from "@revenueos/shared";

const apiBaseUrl = process.env.FULL_STACK_API_URL ?? "http://localhost:8000";

test("briefing preferences survive a new browser context through the real API and PostgreSQL", async ({
  browser,
  request,
}) => {
  const originalResponse = await request.get(
    `${apiBaseUrl}/api/v1/daily/preferences`,
  );
  expect(originalResponse.ok()).toBeTruthy();
  const original =
    (await originalResponse.json()) as DeliveryPreferenceResponse;
  const changedMinutes = original.preMeetingMinutes === 75 ? 76 : 75;
  let persisted: DeliveryPreferenceResponse | null = null;

  try {
    const firstContext = await browser.newContext();
    const firstPage = await firstContext.newPage();
    await firstPage.goto("/settings");
    const firstLeadTime = firstPage.getByLabel("Briefing lead time (minutes)");
    await expect(firstLeadTime).toHaveValue(
      String(original.preMeetingMinutes),
      {
        timeout: 20_000,
      },
    );
    await firstLeadTime.fill(String(changedMinutes));
    await firstPage.getByRole("button", { name: "Save preferences" }).click();
    await expect(
      firstPage.getByText(/Preferences saved privately/i),
    ).toBeVisible();
    await firstContext.close();

    await expect
      .poll(
        async () => {
          const persistedResponse = await request.get(
            `${apiBaseUrl}/api/v1/daily/preferences`,
          );
          if (!persistedResponse.ok()) return null;
          const candidate =
            (await persistedResponse.json()) as DeliveryPreferenceResponse;
          return candidate.preMeetingMinutes;
        },
        {
          message: "the API to expose the committed preference update",
          timeout: 5_000,
        },
      )
      .toBe(changedMinutes);
    const persistedResponse = await request.get(
      `${apiBaseUrl}/api/v1/daily/preferences`,
    );
    expect(persistedResponse.ok()).toBeTruthy();
    persisted = (await persistedResponse.json()) as DeliveryPreferenceResponse;
    expect(persisted.lockVersion).toBe(original.lockVersion + 1);

    const secondContext = await browser.newContext();
    const secondPage = await secondContext.newPage();
    await secondPage.goto("/settings");
    await expect(
      secondPage.getByLabel("Briefing lead time (minutes)"),
    ).toHaveValue(String(changedMinutes), { timeout: 20_000 });
    await secondContext.close();
  } finally {
    if (persisted) {
      const restoreResponse = await request.put(
        `${apiBaseUrl}/api/v1/daily/preferences`,
        {
          data: {
            expectedLockVersion: persisted.lockVersion,
            timezone: original.timezone,
            morningDigestEnabled: original.morningDigestEnabled,
            morningDigestTime: original.morningDigestTime,
            preMeetingEnabled: original.preMeetingEnabled,
            preMeetingMinutes: original.preMeetingMinutes,
            importFromBrowser: false,
          },
        },
      );
      expect(restoreResponse.ok()).toBeTruthy();
    }
  }
});
