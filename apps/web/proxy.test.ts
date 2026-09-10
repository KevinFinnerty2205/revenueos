import type { NextFetchEvent, NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import proxy from "@/proxy";

const handleClerkRequest = vi.hoisted(() => vi.fn(() => new Response()));

vi.mock("@clerk/nextjs/server", () => ({
  clerkMiddleware: () => handleClerkRequest,
}));

function request(pathname: string): NextRequest {
  return { nextUrl: { pathname } } as NextRequest;
}

describe("proxy", () => {
  beforeEach(() => {
    handleClerkRequest.mockClear();
    vi.stubEnv("AUTH_MODE", "clerk");
  });

  it("keeps bearer-link Deal Rooms outside Clerk middleware", () => {
    proxy(request("/deal-room"), {} as NextFetchEvent);
    expect(handleClerkRequest).not.toHaveBeenCalled();
  });

  it.each([
    "/",
    "/platform",
    "/pricing",
    "/integrations",
    "/security",
    "/contact",
    "/privacy",
    "/terms",
  ])("keeps public marketing route %s outside Clerk middleware", (pathname) => {
    proxy(request(pathname), {} as NextFetchEvent);
    expect(handleClerkRequest).not.toHaveBeenCalled();
  });

  it("retains Clerk middleware for application routes", () => {
    const protectedRequest = request("/opportunities");
    const event = {} as NextFetchEvent;
    proxy(protectedRequest, event);
    expect(handleClerkRequest).toHaveBeenCalledWith(protectedRequest, event);
  });

  it("lets an unknown path reach the branded 404 without Clerk", () => {
    proxy(request("/this-page-does-not-exist"), {} as NextFetchEvent);
    expect(handleClerkRequest).not.toHaveBeenCalled();
  });
});
