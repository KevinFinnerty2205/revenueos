export const publicMarketingPaths = [
  "/",
  "/platform",
  "/pricing",
  "/integrations",
  "/security",
  "/contact",
  "/privacy",
  "/terms",
] as const;

const publicMarketingPathSet = new Set<string>(publicMarketingPaths);

const identityAwarePathPrefixes = [
  "/api",
  "/assistant",
  "/billing",
  "/campaigns",
  "/companies",
  "/contacts",
  "/create",
  "/dashboard",
  "/events",
  "/feedback",
  "/find",
  "/insights",
  "/interactions",
  "/meetings",
  "/onboarding",
  "/opportunities",
  "/select-organisation",
  "/settings",
  "/sign-in",
  "/sign-out",
  "/sign-up",
  "/tasks",
  "/trpc",
] as const;

export function isPublicMarketingPath(pathname: string): boolean {
  return publicMarketingPathSet.has(pathname);
}

export function isPublicWebPath(pathname: string): boolean {
  return (
    isPublicMarketingPath(pathname) ||
    pathname === "/deal-room" ||
    pathname.startsWith("/deal-room/") ||
    pathname === "/robots.txt" ||
    pathname === "/sitemap.xml"
  );
}

export function isIdentityAwareWebPath(pathname: string): boolean {
  return identityAwarePathPrefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
