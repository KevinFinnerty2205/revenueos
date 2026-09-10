import type { MetadataRoute } from "next";
import { isSearchIndexingAllowed } from "@/lib/deployment";
import { siteOrigin } from "@/lib/marketing";

const privatePaths = [
  "/assistant",
  "/billing",
  "/campaigns",
  "/companies",
  "/contacts",
  "/create",
  "/dashboard",
  "/deal-room",
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
] as const;

export default function robots(): MetadataRoute.Robots {
  if (!isSearchIndexingAllowed()) {
    return {
      rules: { userAgent: "*", disallow: "/" },
    };
  }
  return {
    rules: {
      userAgent: "*",
      allow: [
        "/",
        "/platform",
        "/pricing",
        "/integrations",
        "/security",
        "/contact",
      ],
      disallow: [...privatePaths, "/privacy", "/terms"],
    },
    sitemap: `${siteOrigin}/sitemap.xml`,
    host: siteOrigin,
  };
}
