import type { Metadata } from "next";
import { ConditionalClerkProvider } from "@/components/conditional-clerk-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "RevenueOS — Sales Brain",
  description:
    "The AI sales teammate that remembers every customer interaction and turns conversations into action.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const content = (
    <html lang="en-AU">
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
