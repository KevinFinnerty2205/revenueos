import { defineConfig, devices } from "@playwright/test";

const webPort = Number(process.env.PLAYWRIGHT_PORT ?? "3000");
const baseURL = `http://127.0.0.1:${webPort}`;
const useExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";

export default defineConfig({
  testDir: "./e2e/actual-browser-media",
  timeout: 45_000,
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  webServer: useExistingServer
    ? undefined
    : {
        command: `pnpm exec next dev --port ${webPort}`,
        url: baseURL,
      },
  projects: [
    {
      name: "chrome-macos-shared-tab-audio",
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
        headless: false,
        launchOptions: {
          args: [
            "--allow-http-screen-capture",
            "--auto-select-tab-capture-source-by-title=Synthetic shared audio source",
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
          ],
        },
        permissions: ["microphone"],
      },
    },
  ],
});
