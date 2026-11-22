import type { Metadata } from "next";
import { auth as clerkAuth, currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { ApiAuthBridge } from "@/components/api-auth-bridge";
import { AppShell } from "@/components/app-shell";
import { VerifiedOrganisationProvider } from "@/components/verified-organisation-context";
import { getAuthState, isRouteAccessAllowed } from "@/lib/auth";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function ProtectedLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const configured = getAuthState();
  if (configured.mode === "mock") {
    if (!isRouteAccessAllowed(configured)) redirect("/sign-in");
    return (
      <VerifiedOrganisationProvider
        identityKey={`${configured.organisation?.id ?? "mock-organisation"}:${configured.user?.id ?? "mock-user"}`}
      >
        <AppShell authState={configured}>{children}</AppShell>
      </VerifiedOrganisationProvider>
    );
  }

  const session = await clerkAuth();
  if (!session.userId) redirect("/sign-in");
  if (!session.orgId) redirect("/select-organisation");

  const identity = await currentUser();
  const clerkState = {
    authenticated: true,
    mode: "clerk" as const,
    user: {
      id: session.userId,
      externalAuthId: session.userId,
      displayName:
        identity?.fullName ?? identity?.firstName ?? "Private beta user",
      email:
        identity?.primaryEmailAddress?.emailAddress ??
        "Identity managed by Clerk",
    },
    organisation: {
      id: session.orgId,
      name: "Active organisation",
      slug: session.orgId,
    },
  };

  return (
    <ApiAuthBridge>
      <VerifiedOrganisationProvider
        identityKey={`${session.orgId}:${session.userId}`}
      >
        <AppShell authState={clerkState}>{children}</AppShell>
      </VerifiedOrganisationProvider>
    </ApiAuthBridge>
  );
}
