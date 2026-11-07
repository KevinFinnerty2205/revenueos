"use client";

import type { Company } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AccountAvatar } from "@/components/account-avatar";
import { AccountConversationPanel } from "@/components/account-conversation-panel";
import { apiRequest } from "@/lib/api";

export function AccountConversations({ companyId }: { companyId: string }) {
  const [company, setCompany] = useState<Company | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<Company>(
      `/api/v1/companies/${encodeURIComponent(companyId)}`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) {
          setCompany(value);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "This company could not be loaded.",
          );
      });
    return () => controller.abort();
  }, [companyId, retry]);
  return (
    <div className="space-y-7">
      <Link
        href="/conversations"
        className="text-sm font-semibold text-brand-primary hover:underline"
      >
        Back to conversations
      </Link>
      {error ? (
        <div role="alert" className="form-card">
          <p>{error}</p>
          <button
            className="secondary-button mt-3"
            onClick={() => setRetry((value) => value + 1)}
          >
            Try again
          </button>
        </div>
      ) : !company || company.id !== companyId ? (
        <p role="status">Loading company…</p>
      ) : (
        <>
          <header className="flex items-center gap-4">
            <AccountAvatar
              accountId={company.id}
              name={company.name}
              website={company.website}
            />
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-brand-primary">
                {company.name}
              </h1>
              <p className="mt-2 text-sm text-brand-muted">
                Your conversations, notes and commitments in one place.
              </p>
            </div>
          </header>
          <AccountConversationPanel companyId={companyId} />
        </>
      )}
    </div>
  );
}
