import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { ConditionalClerkProvider } from "@/components/conditional-clerk-provider";
import "./globals.css";

export const metadata: Metadata = {
  applicationName: "Oryntela",
  title: {
    default: "Oryntela",
    template: "%s | Oryntela",
  },
  description:
    "The AI sales teammate that remembers every customer interaction and turns conversations into action.",
  icons: {
    icon: [
      {
        url: "/brand/oryntela/oryntela-favicon.svg",
        type: "image/svg+xml",
      },
      {
        url: "/brand/oryntela/oryntela-favicon-16.png",
        sizes: "16x16",
        type: "image/png",
      },
      {
        url: "/brand/oryntela/oryntela-favicon-32.png",
        sizes: "32x32",
        type: "image/png",
      },
      {
        url: "/brand/oryntela/oryntela-favicon-48.png",
        sizes: "48x48",
        type: "image/png",
      },
    ],
    shortcut: "/brand/oryntela/oryntela-favicon.ico",
    apple: "/brand/oryntela/oryntela-app-icon-512.png",
  },
  openGraph: {
    title: "Oryntela",
    description:
      "The AI sales teammate that remembers every customer interaction and turns conversations into action.",
    siteName: "Oryntela",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#F6F4EF",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const content = (
    <html className={GeistSans.variable} lang="en-AU">
      <body>{children}</body>
    </html>
  );
  const clerkEnabled =
    ((process.env.AUTH_MODE ?? process.env.NEXT_PUBLIC_AUTH_MODE) === "clerk" ||
      ((process.env.AUTH_MODE ?? process.env.NEXT_PUBLIC_AUTH_MODE) ===
        undefined &&
        process.env.NODE_ENV === "production")) &&
    Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  return (
    <ConditionalClerkProvider enabled={clerkEnabled}>
      {content}
    </ConditionalClerkProvider>
  );
}
