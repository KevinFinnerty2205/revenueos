import { auth as clerkAuth, currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { ApiAuthBridge } from "@/components/api-auth-bridge";
import { AppShell } from "@/components/app-shell";
import { getAuthState, isRouteAccessAllowed } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function ProtectedLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const configured = getAuthState();
  if (configured.mode === "mock") {
    if (!isRouteAccessAllowed(configured)) redirect("/sign-in");
    return <AppShell authState={configured}>{children}</AppShell>;
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
      <AppShell authState={clerkState}>{children}</AppShell>
    </ApiAuthBridge>
  );
}
