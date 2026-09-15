import type { Metadata } from "next";
import { LegalDocument } from "@/components/marketing/legal-document";
import { loadLegalDocument } from "@/lib/legal-documents";
import { createMarketingMetadata } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Privacy Policy",
  "The current Oryntela Privacy Policy, effective 15 September 2026.",
  "/privacy",
);

export default function PrivacyPage() {
  return (
    <LegalDocument
      source={loadLegalDocument("privacy")}
      title="Oryntela Privacy Policy"
    />
  );
}
