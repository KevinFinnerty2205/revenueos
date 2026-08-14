"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type BetaFeature = "opportunityWorkspace" | "revenueBrain" | "aiCompanion";

interface Capabilities {
  featureFlags: Record<string, boolean>;
}

export function BetaFeatureGate({
  feature,
  children,
}: {
  feature: BetaFeature;
  children: React.ReactNode;
}) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<Capabilities>("/api/v1/beta/capabilities", {
      signal: controller.signal,
    })
      .then((capabilities) =>
        setEnabled(capabilities.featureFlags[feature] === true),
      )
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
  }, [feature]);

  if (error || enabled === false) {
    return (
      <section
        className="form-card"
        aria-labelledby="feature-unavailable-title"
      >
        <h1 id="feature-unavailable-title" className="text-2xl font-semibold">
          Feature unavailable
        </h1>
        <p role="status" className="mt-3 text-sm leading-6 text-slate-600">
          This workspace is not enabled for the private beta. Return to the
          dashboard or contact your organisation administrator.
        </p>
      </section>
    );
  }
  if (enabled === null) {
    return (
      <p role="status" className="text-sm text-slate-600">
        Checking workspace availability…
      </p>
    );
  }
  return children;
}
