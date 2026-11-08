import { defineConfig, devices } from "@playwright/test";

const webPort = Number(process.env.PLAYWRIGHT_PORT ?? "3000");
const baseURL = `http://localhost:${webPort}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "conversation-persistence-full-stack.spec.ts",
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `pnpm exec next dev --port ${webPort}`,
    url: baseURL,
    env: {
      NEXT_PUBLIC_SITE_URL: "https://oryntela.com.au",
    },
    reuseExistingServer: true,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
