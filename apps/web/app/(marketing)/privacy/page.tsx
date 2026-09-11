import type { Metadata } from "next";
import { LegalDocument } from "@/components/marketing/legal-document";
import { loadLegalDocument } from "@/lib/legal-documents";
import { createMarketingMetadata } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Privacy Policy — owner review draft",
  "Owner-review draft of the Oryntela Privacy Policy. Not approved or effective.",
  "/privacy",
  { index: false },
);

export default function PrivacyPage() {
  return (
    <LegalDocument
      source={loadLegalDocument("privacy")}
      title="Oryntela Privacy Policy"
    />
  );
}
