export type DeploymentEnvironment =
  "development" | "test" | "staging" | "production";

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
): void {
  assertDeploymentConfiguration(variables);
  const environment = resolveDeploymentEnvironment(
    variables.ORYNTELA_ENVIRONMENT,
  );
  if (environment === "development" || environment === "test") return;
  const secretKey = requireValue(variables, "CLERK_SECRET_KEY");
  if (environment === "production" && !secretKey.startsWith("sk_live_")) {
    throw new Error("Production requires a Clerk production-instance secret.");
  }
  if (
    environment === "production" &&
    !/^[a-f0-9]{40}$/.test(requireValue(variables, "ORYNTELA_RELEASE_SHA"))
  ) {
    throw new Error("Production requires the immutable Git release SHA.");
  }
}

export function isSearchIndexingAllowed(
  value = process.env.ORYNTELA_ENVIRONMENT,
): boolean {
  const environment = resolveDeploymentEnvironment(value);
  return environment === "development" || environment === "production";
}
