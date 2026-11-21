"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export type VerifiedOrganisationState =
  | { status: "loading"; organisationId: null }
  | { status: "available"; organisationId: string }
  | { status: "unavailable"; organisationId: null };

interface OwnedOrganisationState {
  identityKey: string;
  value: VerifiedOrganisationState;
}

const VerifiedOrganisationContext =
  createContext<VerifiedOrganisationState | null>(null);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function organisationIdFromMe(value: unknown): string | null {
  if (!isRecord(value) || !isRecord(value.organisation)) return null;
  const organisationId = value.organisation.id;
  return typeof organisationId === "string" && organisationId.trim()
    ? organisationId
    : null;
}

export function VerifiedOrganisationProvider({
  children,
  identityKey,
}: {
  children: React.ReactNode;
  identityKey: string;
}) {
  const [state, setState] = useState<OwnedOrganisationState>({
    identityKey,
    value: { status: "loading", organisationId: null },
  });

  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<unknown>("/api/v1/me", { signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        const organisationId = organisationIdFromMe(response);
        setState({
          identityKey,
          value: organisationId
            ? { status: "available", organisationId }
            : { status: "unavailable", organisationId: null },
        });
      })
      .catch((reason: unknown) => {
        if (
          controller.signal.aborted ||
          (reason instanceof DOMException && reason.name === "AbortError")
        ) {
          return;
        }
        setState({
          identityKey,
          value: { status: "unavailable", organisationId: null },
        });
      });
    return () => controller.abort();
  }, [identityKey]);

  const value =
    state.identityKey === identityKey
      ? state.value
      : ({ status: "loading", organisationId: null } as const);
  return (
    <VerifiedOrganisationContext.Provider value={value}>
      {children}
    </VerifiedOrganisationContext.Provider>
  );
}

export function useVerifiedOrganisation(): VerifiedOrganisationState {
  return (
    useContext(VerifiedOrganisationContext) ?? {
      status: "unavailable",
      organisationId: null,
    }
  );
}
