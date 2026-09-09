import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { displayPipelineName } from "@/lib/customer-display";

const productionRoots = ["app", "components", "lib"];
const requiredAssets = [
  "oryntela-logo-primary.svg",
  "oryntela-logo-dark.svg",
  "oryntela-logo-white.svg",
  "oryntela-logo-black.svg",
  "oryntela-symbol.svg",
  "oryntela-wordmark.svg",
  "oryntela-favicon.svg",
  "oryntela-favicon.ico",
  "oryntela-favicon-16.png",
  "oryntela-favicon-32.png",
  "oryntela-favicon-48.png",
  "oryntela-app-icon.svg",
  "oryntela-app-icon-512.png",
] as const;

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    if (!/\.(?:ts|tsx)$/u.test(entry) || /\.test\.(?:ts|tsx)$/u.test(entry)) {
      return [];
    }
    return [path];
  });
}

describe("Oryntela production brand surface", () => {
  it("contains no standalone legacy display name, placeholder R, or legacy teal brand utility", () => {
    const failures: string[] = [];
    for (const root of productionRoots) {
      for (const path of sourceFiles(join(process.cwd(), root)).filter(
        (sourcePath) => !sourcePath.endsWith("lib/customer-display.ts"),
      )) {
        const source = readFileSync(path, "utf8");
        if (/\bRevenueOS\b|Revenue OS/u.test(source)) failures.push(path);
        if (/^\s*R\s*$/mu.test(source)) failures.push(path);
        if (/teal-[0-9]+/u.test(source)) failures.push(path);
      }
    }
    expect(failures).toEqual([]);
  });

  it("translates only the persisted legacy default pipeline at the presentation edge", () => {
    expect(displayPipelineName("RevenueOS Sales Pipeline")).toBe(
      "Oryntela Sales Pipeline",
    );
    expect(displayPipelineName("Customer pipeline")).toBe("Customer pipeline");
  });

  it("ships only the approved final identity assets required by product metadata and UI", () => {
    const assetRoot = join(process.cwd(), "public", "brand", "oryntela");
    expect(readdirSync(assetRoot).sort()).toEqual([...requiredAssets].sort());
    for (const asset of requiredAssets) {
      expect(existsSync(join(assetRoot, asset))).toBe(true);
    }
  });

  it("keeps shipped SVG assets local and inert", () => {
    const assetRoot = join(process.cwd(), "public", "brand", "oryntela");
    const svgFiles = requiredAssets.filter((asset) => asset.endsWith(".svg"));
    for (const asset of svgFiles) {
      const source = readFileSync(join(assetRoot, asset), "utf8");
      expect(source).not.toMatch(
        /<script|<foreignObject|\s(?:href|xlink:href|src)\s*=\s*["']https?:\/\//iu,
      );
    }
  });
});
