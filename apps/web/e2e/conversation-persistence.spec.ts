import {
  expect,
  test,
  type BrowserContext,
  type Route,
} from "@playwright/test";

interface PreferenceState {
  exists: boolean;
  lockVersion: number;
  timezone: string;
  morningDigestEnabled: boolean;
  morningDigestTime: string;
  preMeetingEnabled: boolean;
  preMeetingMinutes: number;
  importedFromBrowserAt: string | null;
  updatedAt: string | null;
}

test("private briefing preferences persist across independent browser contexts and reject stale edits", async ({
  browser,
}) => {
  let state: PreferenceState = {
    exists: false,
    lockVersion: 0,
    timezone: "Australia/Sydney",
    morningDigestEnabled: true,
    morningDigestTime: "07:30",
    preMeetingEnabled: true,
    preMeetingMinutes: 30,
    importedFromBrowserAt: null,
    updatedAt: null,
  };

  async function configure(context: BrowserContext) {
    await context.route("http://localhost:8000/api/v1/me", async (route) => {
      await route.fulfill({
        json: {
          user: {
            id: "user-1",
            externalAuthId: "user_dev_001",
            displayName: "Alex Morgan",
            email: "alex@example.test",
          },
          organisation: {
            id: "organisation-1",
            name: "Example Revenue Team",
            slug: "example-revenue-team",
          },
          role: "member",
          authMode: "mock",
          requestId: "request-conversation-persistence-e2e",
        },
      });
    });
    await context.route(
      "http://localhost:8000/api/v1/daily/preferences",
      async (route: Route) => {
        const request = route.request();
        if (request.method() === "GET") {
          await route.fulfill({ json: state });
          return;
        }
        const body = request.postDataJSON() as PreferenceState & {
          expectedLockVersion: number;
          importFromBrowser?: boolean;
        };
        if (body.expectedLockVersion !== state.lockVersion) {
          await route.fulfill({
            status: 409,
            json: {
              code: "delivery_preference_conflict",
              message:
                "Briefing preferences changed in another session. Reload before saving.",
            },
          });
          return;
        }
        state = {
          exists: true,
          lockVersion: state.lockVersion + 1,
          timezone: body.timezone,
          morningDigestEnabled: body.morningDigestEnabled,
          morningDigestTime: body.morningDigestTime,
          preMeetingEnabled: body.preMeetingEnabled,
          preMeetingMinutes: body.preMeetingMinutes,
          importedFromBrowserAt: body.importFromBrowser
            ? "2026-10-31T01:00:00Z"
            : state.importedFromBrowserAt,
          updatedAt: "2026-10-31T01:00:00Z",
        };
        await route.fulfill({ json: state });
      },
    );
  }

  const firstContext = await browser.newContext();
  const secondContext = await browser.newContext();
  try {
    await configure(firstContext);
    await configure(secondContext);
    const firstPage = await firstContext.newPage();
    const secondPage = await secondContext.newPage();

    await firstPage.goto("/settings");
    const firstLeadTime = firstPage.getByLabel("Briefing lead time (minutes)");
    await expect(firstLeadTime).toHaveValue("30");
    await firstLeadTime.fill("75");
    await firstPage.getByRole("button", { name: "Save preferences" }).click();
    await expect(
      firstPage.getByText(/Preferences saved privately/i),
    ).toBeVisible();

    await secondPage.goto("/settings");
    const secondLeadTime = secondPage.getByLabel(
      "Briefing lead time (minutes)",
    );
    await expect(secondLeadTime).toHaveValue("75");

    await firstLeadTime.fill("90");
    await firstPage.getByRole("button", { name: "Save preferences" }).click();
    await expect(
      firstPage.getByText(/Preferences saved privately/i),
    ).toBeVisible();

    await secondLeadTime.fill("120");
    await secondPage.getByRole("button", { name: "Save preferences" }).click();
    await expect(
      secondPage.getByText(
        /changed in another session\. Reload before saving/i,
      ),
    ).toBeVisible();
    await expect(secondLeadTime).toHaveValue("120");
  } finally {
    await firstContext.close();
    await secondContext.close();
  }
});
