"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const primaryItems = [
  { href: "/dashboard", label: "Home" },
  { href: "/conversations", label: "Conversations" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/frameworks", label: "Frameworks" },
] as const;

function isActive(pathname: string | null, href: string) {
  if (!pathname) return false;
  return (
    pathname === href ||
    (href !== "/dashboard" && pathname.startsWith(`${href}/`))
  );
}

export function CoreNavigation() {
  const pathname = usePathname();

  return (
    <>
      <nav aria-label="Main navigation" className="mt-10 hidden lg:block">
        <div className="space-y-1">
          {primaryItems.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`group flex min-h-11 items-center justify-between rounded-xl border-l-2 px-3 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2 ${
                  active
                    ? "border-brand-accent bg-brand-secondary/10 text-brand-primary"
                    : "border-transparent text-brand-muted hover:bg-brand-secondary/8 hover:text-brand-secondary"
                }`}
              >
                {item.label}
                {active ? (
                  <span
                    className="size-1.5 rounded-full bg-brand-accent"
                    aria-hidden="true"
                  />
                ) : null}
              </Link>
            );
          })}
        </div>
        <div className="mt-8 border-t border-brand-primary/10 pt-5">
          <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.12em] text-brand-muted">
            Workspace
          </p>
          {[
            { href: "/assistant", label: "Search / Ask Oryntela" },
            { href: "/settings", label: "Settings" },
          ].map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`block min-h-11 rounded-xl px-3 py-3 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2 ${
                  active
                    ? "bg-brand-secondary/10 text-brand-primary"
                    : "text-brand-muted hover:bg-brand-secondary/8 hover:text-brand-secondary"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <nav
        aria-label="Mobile navigation"
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-brand-primary/10 bg-white/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-10px_30px_rgba(14,27,50,0.08)] backdrop-blur lg:hidden"
      >
        {primaryItems.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-12 items-center justify-center rounded-xl px-1 text-center text-[11px] font-bold focus:outline-none focus:ring-2 focus:ring-brand-focus ${
                active
                  ? "bg-brand-secondary/10 text-brand-primary shadow-[inset_0_-2px_0_var(--brand-accent)]"
                  : "text-brand-muted"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
