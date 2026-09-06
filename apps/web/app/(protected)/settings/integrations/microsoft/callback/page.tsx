import { Suspense } from "react";
import { MicrosoftOAuthCallback } from "@/components/microsoft-oauth-callback";

export default function MicrosoftOAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <p className="p-8 text-sm text-slate-600">
          Loading Microsoft callback…
        </p>
      }
    >
      <MicrosoftOAuthCallback />
    </Suspense>
  );
}
