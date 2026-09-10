import type { MetadataRoute } from "next";
import { siteOrigin } from "@/lib/marketing";

const marketingPages = [
  { path: "", priority: 1 },
  { path: "/platform", priority: 0.9 },
  { path: "/pricing", priority: 0.9 },
  { path: "/integrations", priority: 0.8 },
  { path: "/security", priority: 0.8 },
  { path: "/contact", priority: 0.7 },
] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  return marketingPages.map((page) => ({
    url: `${siteOrigin}${page.path}`,
    lastModified: new Date("2026-09-10T00:00:00+10:00"),
    changeFrequency: "monthly",
    priority: page.priority,
  }));
}
