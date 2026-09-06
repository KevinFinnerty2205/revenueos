"use client";

import type { OrganisationConnection } from "@revenueos/shared";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function MicrosoftOAuthCallback() {
  const searchParams = useSearchParams();
  const oauthState = searchParams.get("state");
  const code = searchParams.get("code");
  const error = searchParams.get("error");
  const description = searchParams.get("error_description") ?? "";
  const providerError =
    error &&
    (error === "admin_consent_required" ||
      description.includes("AADSTS65001") ||
      description.includes("AADSTS65004"))
      ? "admin_consent_required"
      : error;
  const completeResponse = Boolean(oauthState && (code || providerError));
  const [state, setState] = useState<"processing" | "connected" | "failed">(
    completeResponse ? "processing" : "failed",
  );
  const [message, setMessage] = useState(
    completeResponse
      ? "Verifying Microsoft authorisation…"
      : "This Microsoft authorisation response is incomplete. Start the connection again.",
  );

  useEffect(() => {
    if (!oauthState || (!code && !providerError)) return;
    apiRequest<OrganisationConnection>(
      "/api/v1/integrations/microsoft/oauth/callback",
      {
        method: "POST",
        body: JSON.stringify({
          state: oauthState,
          code,
          providerError,
        }),
      },
    )
      .then((connection) => {
        setState("connected");
        setMessage(
          `${connection.externalAccountEmail ?? "Your Microsoft work account"} is connected.`,
        );
      })
      .catch((reason: unknown) => {
        setState("failed");
        setMessage(
          reason instanceof Error
            ? reason.message
            : "Microsoft 365 could not be connected.",
        );
      });
  }, [code, oauthState, providerError]);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <section className="form-card" aria-live="polite">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
          Microsoft 365
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
