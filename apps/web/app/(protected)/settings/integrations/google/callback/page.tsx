import { Suspense } from "react";
import { GoogleOAuthCallback } from "@/components/google-oauth-callback";

export default function GoogleOAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <p className="p-8 text-sm text-slate-600">Loading Google callback…</p>
      }
    >
      <GoogleOAuthCallback />
    </Suspense>
  );
}
