"use client";

import type { MeResponse } from "@revenueos/shared";
import { useEffect, useState } from "react";
import { BetaAdmin } from "@/components/beta-admin";
import { BillingSubscriptionSettings } from "@/components/billing-subscription-settings";
import { CommercialPlanSettings } from "@/components/commercial-plan-settings";
import { CreditsSettings } from "@/components/credits-settings";
import { CRMImportOnboarding } from "@/components/crm-import-onboarding";
import { CRMSettings } from "@/components/crm-settings";
import { EngageSettings } from "@/components/engage-settings";
import { PageHeader } from "@/components/page-header";
import { PipelineSettings } from "@/components/pipeline-settings";
import { ProspectModuleSettings } from "@/components/prospect-module-settings";
import { SalesMethodologySettings } from "@/components/sales-methodology-settings";
import { SellingProfileSettings } from "@/components/selling-profile-settings";
import { apiRequest } from "@/lib/api";

/**
 * Direct-link compatibility surface for pre-refocus administration.
 * It is intentionally absent from default navigation and onboarding.
 */
export function LegacySettingsExperience() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<MeResponse>("/api/v1/me", { signal: controller.signal })
      .then(setMe)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Legacy administration could not be loaded.",
          );
        }
      });
    return () => controller.abort();
  }, []);

  if (error) return <p role="alert">{error}</p>;
  if (!me) return <p role="status">Loading legacy administration…</p>;
  if (me.role !== "admin") {
    return (
      <section className="form-card">
        <h1 className="form-legend">Administrator access required</h1>
        <p className="mt-2 text-sm text-slate-600">
          This compatibility surface is available only to organisation
          administrators.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Direct-link compatibility"
        title="Legacy administration"
        description="Retained administration for existing records and tests. These modules are not part of the default conversation-intelligence journey."
      />
      <SellingProfileSettings />
      <CommercialPlanSettings />
      <BillingSubscriptionSettings />
      <CreditsSettings />
      <ProspectModuleSettings />
      <EngageSettings />
      <CRMSettings />
      <CRMImportOnboarding />
      <PipelineSettings />
      <SalesMethodologySettings />
      <BetaAdmin currentUserId={me.user.id} />
    </div>
  );
}
