import { MarketingShell } from "@/components/marketing/marketing-shell";
import { siteOrigin } from "@/lib/marketing";

const structuredData = [
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Oryntela",
    legalName: "Management Services Australia Pty. Ltd.",
    url: siteOrigin,
    email: "hello@oryntela.com.au",
  },
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Oryntela",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web browser",
    description:
      "An end-to-end sales platform for prospecting, reviewed outreach, CRM, opportunity management, forecasting and handover.",
    url: siteOrigin,
  },
] as const;

export default function MarketingLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <MarketingShell>
      {children}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(structuredData).replaceAll("<", "\\u003c"),
        }}
      />
    </MarketingShell>
  );
}
