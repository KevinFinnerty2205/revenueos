export type DeploymentEnvironment =
  "development" | "test" | "staging" | "production";

export type LegalContentStatus = {
  privacy: "gap" | "draft" | "approved";
  terms: "gap" | "draft" | "approved";
};

// These values describe the copy committed to the public routes. Change either
// value only in the same reviewed change that replaces the corresponding GAP
// page with owner-approved publication copy.
export const legalContentStatus: LegalContentStatus = {
  privacy: "gap",
  terms: "gap",
};

type DeploymentVariables = Readonly<Record<string, string | undefined>>;

export function resolveDeploymentEnvironment(
  value = process.env.ORYNTELA_ENVIRONMENT,
): DeploymentEnvironment {
  if (!value) return "development";
  if (
    value === "development" ||
    value === "test" ||
    value === "staging" ||
    value === "production"
  ) {
    return value;
  }
  throw new Error(`Unsupported ORYNTELA_ENVIRONMENT: ${value}`);
}

function requiredHttpsOrigin(
  variables: DeploymentVariables,
  name: string,
): string {
  const value = variables[name];
  if (!value) throw new Error(`${name} is required for this deployment.`);

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${name} must be an absolute HTTPS origin.`);
  }
  if (
    url.protocol !== "https:" ||
    url.origin !== value ||
    url.username ||
    url.password
  ) {
    throw new Error(`${name} must be an exact public HTTPS origin.`);
  }
  return url.origin;
}

function requireValue(variables: DeploymentVariables, name: string): string {
  const value = variables[name]?.trim();
  if (!value) throw new Error(`${name} is required for this deployment.`);
  return value;
}

export function assertDeploymentConfiguration(
  variables: DeploymentVariables = process.env,
  contentStatus: LegalContentStatus = legalContentStatus,
): void {
  const environment = resolveDeploymentEnvironment(
    variables.ORYNTELA_ENVIRONMENT,
  );
  if (environment === "development" || environment === "test") return;

  const siteOrigin = requiredHttpsOrigin(variables, "NEXT_PUBLIC_SITE_URL");
  const appOrigin = requiredHttpsOrigin(variables, "NEXT_PUBLIC_APP_URL");
  const apiOrigin = requiredHttpsOrigin(variables, "NEXT_PUBLIC_API_BASE_URL");
  if (siteOrigin !== appOrigin) {
    throw new Error(
      "NEXT_PUBLIC_SITE_URL and NEXT_PUBLIC_APP_URL must identify the same canonical origin.",
    );
  }
  if (apiOrigin === appOrigin) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL must identify the separately routed API origin.",
    );
  }
  if (
    variables.AUTH_MODE !== "clerk" ||
    variables.MOCK_AUTH_ENABLED !== "false"
  ) {
    throw new Error(
      "Staging and production require Clerk with mock authentication disabled.",
    );
  }

  const publishableKey = requireValue(
    variables,
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
  );
  if (environment === "production") {
    if (siteOrigin !== "https://oryntela.com.au") {
      throw new Error(
        "Production NEXT_PUBLIC_SITE_URL must be https://oryntela.com.au.",
      );
    }
    if (apiOrigin !== "https://api.oryntela.com.au") {
      throw new Error(
        "Production NEXT_PUBLIC_API_BASE_URL must be https://api.oryntela.com.au.",
      );
    }
    if (!publishableKey.startsWith("pk_live_")) {
      throw new Error("Production requires Clerk production-instance keys.");
    }
    if (
      contentStatus.privacy !== "approved" ||
      contentStatus.terms !== "approved"
    ) {
      throw new Error(
        "Production publication is blocked until Privacy and Terms copy is owner-approved and committed.",
      );
    }
  }
  if (
    variables.ORYNTELA_HSTS_ENABLED === "true" &&
    environment !== "production"
  ) {
    throw new Error(
      "HSTS may be enabled only on the stable production origin.",
    );
  }
}

export function assertWebRuntimeConfiguration(
  variables: DeploymentVariables = process.env,
  contentStatus: LegalContentStatus = legalContentStatus,
): void {
  assertDeploymentConfiguration(variables, contentStatus);
  const environment = resolveDeploymentEnvironment(
    variables.ORYNTELA_ENVIRONMENT,
  );
  if (environment === "development" || environment === "test") return;
  const secretKey = requireValue(variables, "CLERK_SECRET_KEY");
  if (environment === "production" && !secretKey.startsWith("sk_live_")) {
    throw new Error("Production requires a Clerk production-instance secret.");
  }
}

export function isSearchIndexingAllowed(
  value = process.env.ORYNTELA_ENVIRONMENT,
): boolean {
  const environment = resolveDeploymentEnvironment(value);
  return environment === "development" || environment === "production";
}
