import Link from "next/link";
import { BrandLogo } from "@/components/brand-logo";
import { MarketingMobileMenu } from "@/components/marketing/marketing-mobile-menu";
import { marketingNavigation } from "@/lib/marketing";

const footerGroups = [
  {
    heading: "Explore",
    links: [...marketingNavigation, { href: "/contact", label: "Contact" }],
  },
  {
    heading: "Legal",
    links: [
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms" },
    ],
  },
  {
    heading: "Account",
    links: [
      { href: "/sign-in", label: "Sign in" },
      { href: "/contact#trial", label: "Request trial access" },
    ],
  },
] as const;

export function MarketingShell({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="min-h-screen overflow-x-clip bg-brand-background text-brand-text">
      <a
        href="#main-content"
        className="fixed left-4 top-3 z-[100] -translate-y-24 rounded-lg bg-white px-4 py-3 text-sm font-bold text-brand-primary shadow-xl focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-brand-focus"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-50 border-b border-brand-primary/10 bg-brand-background/95 backdrop-blur-xl">
        <div className="mx-auto flex min-h-[76px] max-w-7xl items-center justify-between gap-6 px-5 sm:px-8 lg:px-12">
          <Link
            href="/"
            aria-label="Oryntela home"
            className="inline-flex min-h-11 items-center rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
          >
            <BrandLogo className="h-8 w-auto" decorative />
          </Link>

          <nav aria-label="Primary navigation" className="hidden lg:block">
            <ul className="flex items-center gap-1">
              {marketingNavigation.map((item) => (
                <li key={item.href}>
                  <Link
                    className="inline-flex min-h-11 items-center rounded-full px-4 text-sm font-semibold text-brand-muted transition hover:bg-white hover:text-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-focus"
                    href={item.href}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="hidden items-center gap-2 lg:flex">
            <Link
              href="/sign-in"
              prefetch={false}
              className="inline-flex min-h-11 items-center rounded-full px-4 text-sm font-semibold text-brand-primary transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-brand-focus"
            >
              Sign in
            </Link>
            <Link href="/contact#trial" className="marketing-primary-button">
              Request trial access
            </Link>
          </div>

          <MarketingMobileMenu />
        </div>
      </header>

      <main id="main-content">{children}</main>

      <footer className="border-t border-white/10 bg-brand-primary text-brand-primary-foreground">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 py-14 sm:px-8 md:grid-cols-[1.25fr_1fr] lg:px-12 lg:py-20">
          <div>
            <BrandLogo className="h-8 w-auto" decorative variant="dark" />
            <p className="mt-5 max-w-md text-sm leading-7 text-slate-300">
              The end-to-end sales platform for Australian B2B teams that want
              one clear process from prospect to handover.
            </p>
            <a
              className="mt-5 inline-flex min-h-11 items-center rounded-lg text-sm font-semibold text-white underline decoration-brand-accent decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-accent"
              href="mailto:hello@oryntela.com.au"
            >
              hello@oryntela.com.au
            </a>
          </div>
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
            {footerGroups.map((group) => (
              <nav key={group.heading} aria-label={`${group.heading} links`}>
                <h2 className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">
                  {group.heading}
                </h2>
                <ul className="mt-4 space-y-3">
                  {group.links.map((link) => (
                    <li key={link.href}>
                      <Link
                        className="inline-flex min-h-8 items-center rounded text-sm text-slate-200 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-brand-accent"
                        href={link.href}
                        prefetch={link.href !== "/sign-in"}
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </div>
        <div className="border-t border-white/10 px-5 py-6 text-center text-xs leading-6 text-slate-400 sm:px-8">
          Oryntela is operated by Management Services Australia Pty. Ltd. · ABN
          15 113 119 556
        </div>
      </footer>
    </div>
  );
}
