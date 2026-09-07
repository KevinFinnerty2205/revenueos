import { Suspense } from "react";
import { SalesforceOAuthCallback } from "@/components/salesforce-oauth-callback";

export default function SalesforceOAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <p className="p-8 text-sm text-slate-600">
          Loading Salesforce callback…
        </p>
      }
    >
      <SalesforceOAuthCallback />
    </Suspense>
  );
}
