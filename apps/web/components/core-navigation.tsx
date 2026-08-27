"use client";

import type {
  EngageAvailability,
  CreateAvailability,
  ProspectAvailability,
} from "@revenueos/shared";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

const desktopGroups = [
  {
    label: null,
    items: [{ href: "/dashboard", label: "Home" }],
  },
  {
    label: "Sell",
    items: [
      { href: "/companies", label: "Accounts" },
      { href: "/contacts", label: "People" },
      { href: "/interactions", label: "Interactions" },
    ],
  },
  {
    label: null,
    items: [{ href: "/opportunities", label: "Pipeline" }],
  },
] as const;

const mobileItems = [
  { href: "/dashboard", label: "Today" },
  { href: "/interactions", label: "Interactions" },
  { href: "/dashboard#daily-actions", label: "Actions" },
  { href: "/assistant", label: "Search" },
] as const;

interface BetaCapabilities {
  featureFlags: Record<string, boolean>;
}

function isActive(pathname: string | null, href: string) {
  if (href.includes("#")) return false;
  const path = href.split("#", 1)[0];
  if (!pathname) return false;
  return (
    pathname === path ||
    (path !== "/dashboard" && pathname.startsWith(`${path}/`))
  );
}

export function CoreNavigation() {
  const pathname = usePathname();
  const [prospectEnabled, setProspectEnabled] = useState(false);
  const [engageEnabled, setEngageEnabled] = useState(false);
  const [eventsEnabled, setEventsEnabled] = useState(false);
  const [createEnabled, setCreateEnabled] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ProspectAvailability>("/api/v1/prospect/availability", {
      signal: controller.signal,
    })
      .then((availability) => setProspectEnabled(availability.enabled))
      .catch(() => setProspectEnabled(false));
    apiRequest<EngageAvailability>("/api/v1/engage/availability", {
      signal: controller.signal,
    })
      .then((availability) => setEngageEnabled(availability.enabled))
      .catch(() => setEngageEnabled(false));
    apiRequest<BetaCapabilities>("/api/v1/beta/capabilities", {
      signal: controller.signal,
    })
      .then((capabilities) =>
        setEventsEnabled(capabilities.featureFlags.engageEvents === true),
      )
      .catch(() => setEventsEnabled(false));
    apiRequest<CreateAvailability>("/api/v1/create/availability", {
      signal: controller.signal,
    })
      .then((availability) => setCreateEnabled(availability.enabled))
      .catch(() => setCreateEnabled(false));
    return () => controller.abort();
  }, []);

  const sellGroup = {
    ...desktopGroups[1],
    items: engageEnabled
      ? [
          ...desktopGroups[1].items,
          { href: "/campaigns", label: "Campaigns" },
          ...(eventsEnabled ? [{ href: "/events", label: "Events" }] : []),
        ]
      : desktopGroups[1].items,
  };
  const baseGroups = [desktopGroups[0], sellGroup, desktopGroups[2]];
  const moduleGroups = prospectEnabled
    ? [
        baseGroups[0],
        { label: "Prospect", items: [{ href: "/find", label: "Find" }] },
        ...baseGroups.slice(1),
      ]
    : baseGroups;
  const navigationGroups = createEnabled
    ? [
        ...moduleGroups,
        { label: "Create", items: [{ href: "/create", label: "Studio" }] },
      ]
    : moduleGroups;

  return (
    <>
      <nav aria-label="Main navigation" className="mt-10 hidden lg:block">
        <div className="space-y-7">
          {navigationGroups.map((group, index) => (
            <div key={group.label ?? `group-${index}`}>
              {group.label ? (
                <p className="mb-2 px-3 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-400">
                  {group.label}
                </p>
              ) : null}
              <div className="space-y-1">
                {group.items.map((item) => {
                  const active = isActive(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`block rounded-xl px-3 py-2.5 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 ${
                        active
                          ? "bg-teal-50 text-teal-900"
                          : "text-slate-600 hover:bg-teal-50 hover:text-teal-800"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-8 border-t border-slate-200 pt-5">
          <p className="mb-2 px-3 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-400">
            Workspace
          </p>
          {[
            { href: "/assistant", label: "Search" },
            { href: "/settings", label: "Settings" },
          ].map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`block rounded-xl px-3 py-2.5 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 ${
                  active
                    ? "bg-teal-50 text-teal-900"
                    : "text-slate-600 hover:bg-teal-50 hover:text-teal-800"
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
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-slate-200 bg-white/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-10px_30px_rgba(15,23,42,0.08)] backdrop-blur lg:hidden"
      >
        {mobileItems.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.label}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-12 items-center justify-center rounded-xl px-1 text-center text-xs font-bold focus:outline-none focus:ring-2 focus:ring-teal-600 ${
                active ? "bg-teal-50 text-teal-900" : "text-slate-600"
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
