"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { usePathname } from "next/navigation";

export function ConditionalClerkProvider({
  children,
  enabled,
}: Readonly<{ children: React.ReactNode; enabled: boolean }>) {
  const pathname = usePathname();
  const publicDealRoom =
    pathname === "/deal-room" || pathname.startsWith("/deal-room/");
  return enabled && !publicDealRoom ? (
    <ClerkProvider>{children}</ClerkProvider>
  ) : (
    children
  );
}
