"use client";

import type { OrganisationConnection } from "@revenueos/shared";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function HubSpotOAuthCallback() {
  const searchParams = useSearchParams();
  const oauthState = searchParams.get("state");
  const code = searchParams.get("code");
  const providerError = searchParams.get("error");
  const completeResponse = Boolean(oauthState && (code || providerError));
  const [state, setState] = useState<"processing" | "connected" | "failed">(
    completeResponse ? "processing" : "failed",
  );
  const [message, setMessage] = useState(
    completeResponse
      ? "Verifying HubSpot authorisation…"
      : "This HubSpot authorisation response is incomplete. Start the connection again.",
  );

  useEffect(() => {
    if (!oauthState || (!code && !providerError)) return;
    apiRequest<OrganisationConnection>(
      "/api/v1/integrations/hubspot/oauth/callback",
      {
        method: "POST",
        body: JSON.stringify({ state: oauthState, code, providerError }),
      },
    )
      .then((connection) => {
        setState("connected");
        setMessage(
          `HubSpot account ${connection.externalAccountName ?? connection.externalAccountId ?? ""} is connected.`,
        );
      })
      .catch((reason: unknown) => {
        setState("failed");
        setMessage(
          reason instanceof Error
            ? reason.message
            : "HubSpot could not be connected.",
        );
      });
  }, [code, oauthState, providerError]);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <section className="form-card" aria-live="polite">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
          HubSpot OAuth
        </p>
        <h1 className="mt-2 text-2xl font-bold text-slate-950">
          {state === "processing"
            ? "Connecting…"
            : state === "connected"
              ? "Connected"
              : "Connection not completed"}
        </h1>
        <p
          className={`mt-3 text-sm ${state === "failed" ? "text-rose-800" : "text-slate-600"}`}
        >
          {message}
        </p>
        {state !== "processing" ? (
          <Link className="primary-button mt-5 inline-flex" href="/settings">
            Return to settings
          </Link>
        ) : null}
      </section>
    </main>
  );
}
