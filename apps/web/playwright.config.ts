import { defineConfig, devices } from "@playwright/test";

const webPort = Number(process.env.PLAYWRIGHT_PORT ?? "3000");
const baseURL = `http://localhost:${webPort}`;

export default defineConfig({
  testDir: "./e2e",
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `pnpm exec next dev --port ${webPort}`,
    url: baseURL,
    env: {
      // Keep the public SEO contract deterministic even when a developer's
      // ignored .env.local points browser navigation at localhost.
      NEXT_PUBLIC_SITE_URL: "https://oryntela.com.au",
    },
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
