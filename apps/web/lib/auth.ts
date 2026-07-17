import type {
  AuthMode,
  MeResponse,
  OrganisationSummary,
  UserSummary,
} from "@revenueos/shared";

type RuntimeEnvironment = "development" | "test" | "production";

export interface AuthState {
  authenticated: boolean;
  mode: AuthMode;
  user: UserSummary | null;
  organisation: OrganisationSummary | null;
  message?: string;
}

export interface AuthEnvironment {
  NODE_ENV?: string;
  AUTH_MODE?: string;
  MOCK_AUTH_ENABLED?: string;
  NEXT_PUBLIC_AUTH_MODE?: string;
  NEXT_PUBLIC_MOCK_AUTH_ENABLED?: string;
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?: string;
  CLERK_SECRET_KEY?: string;
}

interface AuthAdapter {
  getState(): AuthState;
}

class DevelopmentAuthAdapter implements AuthAdapter {
  getState(): AuthState {
    return {
      authenticated: true,
      mode: "mock",
      user: {
        id: "00000000-0000-4000-8000-000000000001",
        externalAuthId: "user_dev_001",
        displayName: "Alex Morgan",
        email: "alex@example.test",
      },
      organisation: {
        id: "00000000-0000-4000-8000-000000000002",
        name: "Example Revenue Team",
        slug: "example-revenue-team",
      },
    };
  }
}

class ClerkAuthAdapter implements AuthAdapter {
  constructor(private readonly configured: boolean) {}

  getState(): AuthState {
    return {
      authenticated: false,
      mode: "clerk",
      user: null,
      organisation: null,
      message: this.configured
        ? "Clerk session handling is not connected in the Sprint 1 foundation."
        : "Clerk authentication is not configured.",
    };
  }
}

function runtimeEnvironment(value: string | undefined): RuntimeEnvironment {
  if (value === "production" || value === "test") {
    return value;
  }
  return "development";
}

function enabled(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) {
    return fallback;
  }
  return value.toLowerCase() === "true";
}

export function resolveAuthState(environment: AuthEnvironment): AuthState {
  const runtime = runtimeEnvironment(environment.NODE_ENV);
  const requestedMode =
    environment.AUTH_MODE ??
    environment.NEXT_PUBLIC_AUTH_MODE ??
    (runtime === "production" ? "clerk" : "mock");

  if (requestedMode === "mock") {
    const mockEnabled = enabled(
      environment.MOCK_AUTH_ENABLED ??
        environment.NEXT_PUBLIC_MOCK_AUTH_ENABLED,
      runtime !== "production",
    );
    if (!mockEnabled || runtime === "production") {
      return {
        authenticated: false,
        mode: "mock",
        user: null,
        organisation: null,
        message:
          "Mock authentication is disabled and is never available in production.",
      };
    }
    return new DevelopmentAuthAdapter().getState();
  }

  const configured = Boolean(
    environment.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
    environment.CLERK_SECRET_KEY,
  );
  return new ClerkAuthAdapter(configured).getState();
}

export function getAuthState(): AuthState {
  return resolveAuthState(process.env);
}

export function isRouteAccessAllowed(state: AuthState): boolean {
  return (
    state.authenticated && state.user !== null && state.organisation !== null
  );
}

export function toMeResponse(
  state: AuthState,
  requestId = "web-development",
): MeResponse {
  if (!isRouteAccessAllowed(state) || !state.user || !state.organisation) {
    throw new Error(state.message ?? "Authentication is required.");
  }
  return {
    user: state.user,
    organisation: state.organisation,
    role: "admin",
    authMode: state.mode,
    requestId,
  };
}
