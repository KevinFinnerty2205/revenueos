import type { Metadata } from "next";
import { LegalDocument } from "@/components/marketing/legal-document";
import { loadLegalDocument } from "@/lib/legal-documents";
import { createMarketingMetadata } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Terms & Conditions",
  "The current Oryntela Terms & Conditions, effective 15 September 2026.",
  "/terms",
);

export default function TermsPage() {
  return (
    <LegalDocument
      source={loadLegalDocument("terms")}
      title="Oryntela Terms & Conditions"
    />
  );
}
