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

  it.each([
    "/assistant",
    "/billing/success",
    "/campaigns/campaign-1/enrollments",
    "/companies/company-1/edit",
    "/contacts/contact-1/edit",
    "/create/business-cases/case-1",
    "/dashboard",
    "/events/event-1",
    "/feedback",
    "/find/target-markets/market-1",
    "/insights",
    "/interactions/interaction-1/companion",
    "/meetings/meeting-1/edit",
    "/onboarding",
    "/opportunities/opportunity-1/deal-room",
    "/select-organisation",
    "/settings/integrations/google/callback",
    "/sign-in/sso-callback",
    "/sign-out",
    "/sign-up/verify",
    "/tasks/task-1/edit",
    "/api/v1/deal-rooms/public/resolve",
    "/trpc/private-query",
  ])("retains Clerk middleware for application path %s", (pathname) => {
    const protectedRequest = request(pathname);
    const event = {} as NextFetchEvent;
    proxy(protectedRequest, event);
    expect(handleClerkRequest).toHaveBeenCalledWith(protectedRequest, event);
  });

  it.each([
    "/opportunities-public",
    "/settings-guide",
    "/dashboarding",
    "/deal-roomish",
  ])("does not classify prefix lookalike %s as an app route", (pathname) => {
    proxy(request(pathname), {} as NextFetchEvent);
    expect(handleClerkRequest).not.toHaveBeenCalled();
  });

  it("lets an unknown path reach the branded 404 without Clerk", () => {
    proxy(request("/this-page-does-not-exist"), {} as NextFetchEvent);
    expect(handleClerkRequest).not.toHaveBeenCalled();
  });
});
