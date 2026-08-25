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
    reuseExistingServer: !process.env.CI,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
