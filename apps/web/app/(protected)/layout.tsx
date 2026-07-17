import { AppShell } from "@/components/app-shell";
import { getAuthState, isRouteAccessAllowed } from "@/lib/auth";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default function ProtectedLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const auth = getAuthState();

  if (!isRouteAccessAllowed(auth)) {
    redirect("/sign-in");
  }

  return <AppShell>{children}</AppShell>;
}
