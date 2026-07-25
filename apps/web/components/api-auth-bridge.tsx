"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { configureApiTokenProvider } from "@/lib/api";

export function ApiAuthBridge({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded } = useAuth();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isLoaded) return;
    const template = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE;
    configureApiTokenProvider(() =>
      getToken(template ? { template } : undefined),
    );
    const readyTimer = window.setTimeout(() => setReady(true), 0);
    return () => {
      window.clearTimeout(readyTimer);
      configureApiTokenProvider(null);
    };
  }, [getToken, isLoaded]);

  if (!ready) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f5f7f4] px-5">
        <p role="status" className="text-sm font-semibold text-slate-600">
          Preparing your secure workspace…
        </p>
      </main>
    );
  }
  return children;
}
