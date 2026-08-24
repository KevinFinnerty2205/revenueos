import { Suspense } from "react";
import { HubSpotOAuthCallback } from "@/components/hubspot-oauth-callback";

export default function HubSpotOAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <p className="p-8 text-sm text-slate-600">Loading HubSpot callback…</p>
      }
    >
      <HubSpotOAuthCallback />
    </Suspense>
  );
}
