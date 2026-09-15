import { describe, expect, it } from "vitest";
import { loadLegalDocument } from "@/lib/legal-documents";

describe("canonical legal documents", () => {
  it.each([
    [
      "terms",
      "# Oryntela Terms & Conditions",
      "## 20. Liability",
      "AUD $2,000 per year including GST",
    ],
    [
      "privacy",
      "# Oryntela Privacy Policy",
      "## 9. Retention, export and deletion",
      "Stripe customer billing is disabled",
    ],
  ] as const)(
    "loads the complete approved %s release",
    (name, title, section, currentFact) => {
      const source = loadLegalDocument(name);
      expect(source).toContain(title);
      expect(source).toContain(section);
      expect(source).toContain(currentFact);
      expect(source).toContain("OWNER APPROVED — effective 2026-09-15");
      expect(source).toContain("Version: 2026-09-15");
      expect(source).not.toContain("OWNER REVIEW DRAFT");
      expect(source.match(/\[[^\]]+\]/gu)).toBeNull();
      expect(source).not.toMatch(/RevenueOS/iu);
      expect(source).not.toMatch(/Service Terms not yet published/iu);
    },
  );
});
