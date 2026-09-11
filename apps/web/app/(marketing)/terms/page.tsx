import type { Metadata } from "next";
import { LegalDocument } from "@/components/marketing/legal-document";
import { loadLegalDocument } from "@/lib/legal-documents";
import { createMarketingMetadata } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Terms & Conditions — owner review draft",
  "Owner-review draft of the Oryntela Terms & Conditions. Not approved or effective.",
  "/terms",
  { index: false },
);

export default function TermsPage() {
  return (
    <LegalDocument
      source={loadLegalDocument("terms")}
      title="Oryntela Terms & Conditions"
    />
  );
}
