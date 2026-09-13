type ClerkKeyEnvironment = "live" | "test";

type DecodedClerkPublishableKey = Readonly<{
  environment: ClerkKeyEnvironment;
  origin: string;
}>;

const clerkHostnamePattern =
  /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;

function decodeClerkPublishableKey(
  publishableKey: string,
): DecodedClerkPublishableKey {
  const match = /^pk_(live|test)_([A-Za-z0-9_-]+)$/.exec(publishableKey.trim());
  if (!match) {
    throw new Error("Clerk publishable key has an invalid format.");
  }

  const [, matchedEnvironment, encodedFrontendApi] = match;
  const environment: ClerkKeyEnvironment =
    matchedEnvironment === "live" ? "live" : "test";
  let decoded: string;
  try {
    decoded = Buffer.from(encodedFrontendApi, "base64url").toString("utf8");
  } catch {
    throw new Error("Clerk publishable key Frontend API cannot be decoded.");
  }

  if (!decoded.endsWith("$")) {
    throw new Error("Clerk publishable key Frontend API is malformed.");
  }

  const hostname = decoded.slice(0, -1);
  if (!clerkHostnamePattern.test(hostname)) {
    throw new Error("Clerk publishable key Frontend API hostname is invalid.");
  }

  return {
    environment,
    origin: `https://${hostname}`,
  };
}

export function resolveProductionClerkFrontendApiOrigin(
  publishableKey: string,
  siteOrigin: string,
): string {
  const decoded = decodeClerkPublishableKey(publishableKey);
  if (decoded.environment !== "live") {
    throw new Error("Production requires a Clerk live publishable key.");
  }

  let canonicalSite: URL;
  try {
    canonicalSite = new URL(siteOrigin);
  } catch {
    throw new Error(
      "Production Clerk origin requires a valid canonical site origin.",
    );
  }
  if (
    canonicalSite.protocol !== "https:" ||
    canonicalSite.origin !== siteOrigin ||
    canonicalSite.hostname !== "oryntela.com.au"
  ) {
    throw new Error(
      "Production Clerk origin requires the canonical Oryntela HTTPS site origin.",
    );
  }

  const expectedOrigin = `https://clerk.${canonicalSite.hostname}`;
  if (decoded.origin !== expectedOrigin) {
    throw new Error(
      "Production Clerk publishable key must resolve to the canonical Oryntela Clerk origin.",
    );
  }

  return decoded.origin;
}
