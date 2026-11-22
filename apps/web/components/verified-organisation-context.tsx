"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { apiRequest } from "@/lib/api";

type VerifiedOrganisationSnapshot =
  | { status: "loading"; organisationId: null; userId: null }
  | { status: "available"; organisationId: string; userId: string }
  | { status: "unavailable"; organisationId: null; userId: null };

export type VerifiedOrganisationState = VerifiedOrganisationSnapshot & {
  identityKey: string;
  reload: () => void;
};

interface OwnedOrganisationState {
  identityKey: string;
  value: VerifiedOrganisationSnapshot;
}

const VerifiedOrganisationContext =
  createContext<VerifiedOrganisationState | null>(null);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function identityFromMe(
  value: unknown,
): { organisationId: string; userId: string } | null {
  if (
    !isRecord(value) ||
    !isRecord(value.organisation) ||
    !isRecord(value.user)
  ) {
    return null;
  }
  const organisationId = value.organisation.id;
  const userId = value.user.id;
  if (
    typeof organisationId !== "string" ||
    !organisationId.trim() ||
    typeof userId !== "string" ||
    !userId.trim()
  ) {
    return null;
  }
  return { organisationId, userId };
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
    value: { status: "loading", organisationId: null, userId: null },
  });
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => {
    setState({
      identityKey,
      value: { status: "loading", organisationId: null, userId: null },
    });
    setReloadKey((current) => current + 1);
  }, [identityKey]);

  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<unknown>("/api/v1/me", { signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        const identity = identityFromMe(response);
        setState({
          identityKey,
          value: identity
            ? { status: "available", ...identity }
            : { status: "unavailable", organisationId: null, userId: null },
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
          value: {
            status: "unavailable",
            organisationId: null,
            userId: null,
          },
        });
      });
    return () => controller.abort();
  }, [identityKey, reloadKey]);

  const value =
    state.identityKey === identityKey
      ? state.value
      : ({ status: "loading", organisationId: null, userId: null } as const);
  return (
    <VerifiedOrganisationContext.Provider
      value={{ ...value, identityKey, reload }}
    >
      {children}
    </VerifiedOrganisationContext.Provider>
  );
}

export function useVerifiedOrganisation(): VerifiedOrganisationState {
  const value = useContext(VerifiedOrganisationContext);
  return (
    value ?? {
      status: "unavailable",
      organisationId: null,
      userId: null,
      identityKey: "unavailable",
      reload: () => undefined,
    }
  );
}
