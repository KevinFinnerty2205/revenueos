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

  it("retains Clerk middleware for application routes", () => {
    const protectedRequest = request("/opportunities");
    const event = {} as NextFetchEvent;
    proxy(protectedRequest, event);
    expect(handleClerkRequest).toHaveBeenCalledWith(protectedRequest, event);
  });
});
