"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { apiRequest } from "@/lib/api";

type BetaFeature =
  | "opportunityWorkspace"
  | "revenueBrain"
  | "aiCompanion"
  | "aiDebrief"
  | "voiceJournal"
  | "visualEvidence"
  | "presentationMode"
  | "recordingCapture"
  | "onlineMeetingCapture"
  | "documentEvidence"
  | "emailEvidence";

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
  const titleId = useId();

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
      <section className="form-card" aria-labelledby={titleId}>
        <h2 id={titleId} className="text-xl font-semibold">
          {error
            ? "This section could not be checked"
            : "This section is not enabled"}
        </h2>
        <p
          role={error ? "alert" : "status"}
          className="mt-3 text-sm leading-6 text-slate-600"
        >
          {error
            ? "Try loading the page again. Your other workspace information is still available."
            : "Ask your organisation administrator if this private-beta capability should be available."}
        </p>
        <Link href="/dashboard" className="secondary-button mt-4">
          Return Home
        </Link>
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
