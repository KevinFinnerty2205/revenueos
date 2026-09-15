import { resolveProductionClerkFrontendApiOrigin } from "./clerk-origin";
import { resolveDeploymentEnvironment } from "./deployment";

type CspVariables = Readonly<Record<string, string | undefined>>;

const clerkChallengeOrigin = "https://challenges.cloudflare.com";
const clerkProtectionOrigin = "https://*.protect.clerk.com";
const clerkProtectionConnectOrigin = "https://*.protect.clerk.com:*";
const developmentClerkOrigins = [
  "https://*.clerk.accounts.dev",
  "https://*.clerk.com",
] as const;

function requiredValue(variables: CspVariables, name: string): string {
  const value = variables[name]?.trim();
  if (!value)
    throw new Error(`${name} is required to build the production CSP.`);
  return value;
}

function resolveApiOrigin(
  variables: CspVariables,
  isProduction: boolean,
): string {
  const configured =
    variables.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  let parsed: URL;
  try {
    parsed = new URL(configured);
  } catch {
    throw new Error("Production CSP requires a valid API HTTPS origin.");
  }
  if (
    isProduction &&
    (parsed.protocol !== "https:" ||
      parsed.origin !== configured ||
      parsed.origin !== "https://api.oryntela.com.au")
  ) {
    throw new Error(
      "Production CSP requires the canonical Oryntela API HTTPS origin.",
    );
  }
  return parsed.origin;
}

export function buildContentSecurityPolicy(
  variables: CspVariables = process.env,
): string {
  const deploymentEnvironment = resolveDeploymentEnvironment(
    variables.ORYNTELA_ENVIRONMENT,
  );
  const isProduction = deploymentEnvironment === "production";
  const apiOrigin = resolveApiOrigin(variables, isProduction);
  const clerkFrontendApiOrigin = isProduction
    ? resolveProductionClerkFrontendApiOrigin(
        requiredValue(variables, "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"),
        requiredValue(variables, "NEXT_PUBLIC_SITE_URL"),
      )
    : null;
  const clerkScriptOrigins = isProduction
    ? [clerkFrontendApiOrigin, clerkChallengeOrigin, clerkProtectionOrigin]
    : [...developmentClerkOrigins, clerkChallengeOrigin, clerkProtectionOrigin];
  const clerkConnectOrigins = isProduction
    ? [clerkFrontendApiOrigin, clerkProtectionConnectOrigin]
    : [...developmentClerkOrigins, clerkProtectionConnectOrigin];

  return [
    "default-src 'self'",
    "base-uri 'self'",
    `connect-src 'self' ${apiOrigin} ${clerkConnectOrigins.join(" ")}`,
    "font-src 'self' data:",
    "form-action 'self'",
    "frame-ancestors 'none'",
    `frame-src 'self' ${clerkChallengeOrigin} ${clerkProtectionOrigin}`,
    "img-src 'self' blob: data: https:",
    "object-src 'none'",
    `script-src 'self' 'unsafe-inline'${isProduction ? "" : " 'unsafe-eval'"} ${clerkScriptOrigins.join(" ")}`,
    "style-src 'self' 'unsafe-inline'",
    "worker-src 'self' blob:",
  ].join("; ");
}
