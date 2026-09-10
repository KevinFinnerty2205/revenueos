"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { isIdentityAwareWebPath } from "@/lib/public-routes";

export function ConditionalClerkProvider({
  children,
  enabled,
}: Readonly<{ children: React.ReactNode; enabled: boolean }>) {
  const pathname = usePathname();
  const identityAwareSurface =
    pathname !== null && isIdentityAwareWebPath(pathname);
  return enabled && identityAwareSurface ? (
    <ClerkProvider>{children}</ClerkProvider>
  ) : (
    children
  );
}
