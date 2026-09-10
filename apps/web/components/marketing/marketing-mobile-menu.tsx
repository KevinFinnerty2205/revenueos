"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { marketingNavigation } from "@/lib/marketing";

const focusableSelector =
  'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function MarketingMobileMenu() {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const navigationRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusFrame = window.requestAnimationFrame(() => {
      navigationRef.current
        ?.querySelector<HTMLElement>(focusableSelector)
        ?.focus();
    });

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        window.requestAnimationFrame(() => buttonRef.current?.focus());
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = Array.from(
        navigationRef.current?.querySelectorAll<HTMLElement>(
          focusableSelector,
        ) ?? [],
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className="relative lg:hidden">
      <button
        ref={buttonRef}
        type="button"
        aria-controls="marketing-mobile-navigation"
        aria-expanded={open}
        aria-label={open ? "Close menu" : "Open menu"}
        className="flex min-h-11 cursor-pointer items-center gap-2 rounded-full border border-brand-primary/15 bg-white px-4 text-sm font-bold text-brand-primary shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-focus"
        onClick={() => setOpen((current) => !current)}
      >
        <span>{open ? "Close" : "Menu"}</span>
        <span
          aria-hidden="true"
          className={`text-lg leading-none transition ${open ? "rotate-45" : ""}`}
        >
          +
        </span>
      </button>
      {open ? (
        <nav
          ref={navigationRef}
          id="marketing-mobile-navigation"
          aria-label="Mobile navigation"
          className="absolute right-0 top-14 w-[min(20rem,calc(100vw-2.5rem))] rounded-3xl border border-brand-primary/10 bg-white p-3 shadow-2xl"
        >
          <ul className="grid gap-1">
            {[
              ...marketingNavigation,
              { href: "/contact", label: "Contact" },
            ].map((item) => (
              <li key={item.href}>
                <Link
                  className="flex min-h-12 items-center rounded-2xl px-4 text-base font-semibold text-brand-primary hover:bg-brand-background focus:outline-none focus:ring-2 focus:ring-brand-focus"
                  href={item.href}
                  onClick={() => setOpen(false)}
                >
                  {item.label}
                </Link>
              </li>
            ))}
            <li className="mt-2 border-t border-brand-primary/10 pt-3">
              <Link
                className="marketing-primary-button flex w-full"
                href="/contact#trial"
                onClick={() => setOpen(false)}
              >
                Request trial access
              </Link>
            </li>
            <li>
              <Link
                className="flex min-h-11 items-center justify-center rounded-full px-4 text-sm font-bold text-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-focus"
                href="/sign-in"
                prefetch={false}
                onClick={() => setOpen(false)}
              >
                Sign in
              </Link>
            </li>
          </ul>
        </nav>
      ) : null}
    </div>
  );
}
