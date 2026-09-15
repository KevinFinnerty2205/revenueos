import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

export type LegalDocumentName = "privacy" | "terms";

const documentFiles: Record<LegalDocumentName, string> = {
  privacy: "oryntela-privacy-policy.md",
  terms: "oryntela-terms-and-conditions.md",
};

function legalDocumentPath(name: LegalDocumentName): string {
  const relativePath = `docs/00-company/${documentFiles[name]}`;
  const candidates = [
    resolve(process.cwd(), relativePath),
    resolve(process.cwd(), "../..", relativePath),
  ];
  const match = candidates.find((candidate) => existsSync(candidate));
  if (!match) {
    throw new Error(`Canonical legal document is unavailable: ${relativePath}`);
  }
  return match;
}

export function loadLegalDocument(name: LegalDocumentName): string {
  return readFileSync(legalDocumentPath(name), "utf8");
}
