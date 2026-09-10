import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "@/app/health/ready/route";

describe("web readiness", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("returns a safe response for local configuration", async () => {
    vi.stubEnv("ORYNTELA_ENVIRONMENT", "test");
    const response = GET();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ready" });
  });

  it("does not disclose production configuration failures", async () => {
    vi.stubEnv("ORYNTELA_ENVIRONMENT", "production");
    const response = GET();
    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({ status: "not_ready" });
  });
});
