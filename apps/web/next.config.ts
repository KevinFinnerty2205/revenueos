import type { NextConfig } from "next";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  assertDeploymentConfiguration,
  resolveDeploymentEnvironment,
} from "./lib/deployment";
import { buildContentSecurityPolicy } from "./lib/content-security-policy";

assertDeploymentConfiguration();

const deploymentEnvironment = resolveDeploymentEnvironment();
const isProduction = deploymentEnvironment === "production";
const isStaging = deploymentEnvironment === "staging";

const contentSecurityPolicy = buildContentSecurityPolicy();

const securityHeaders = [
  { key: "Cache-Control", value: "no-store" },
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(self), geolocation=(), payment=()",
  },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  ...(isStaging
    ? [{ key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" }]
    : []),
  ...(isProduction && process.env.ORYNTELA_HSTS_ENABLED === "true"
    ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }]
    : []),
];

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: join(dirname(fileURLToPath(import.meta.url)), "../.."),
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [
      { source: "/(.*)", headers: securityHeaders },
      {
        source: "/deal-room",
        headers: [
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
        ],
      },
    ];
  },
};

export default nextConfig;
