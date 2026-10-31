import Link from "next/link";
import { OrganizationSwitcher } from "@clerk/nextjs";
import { BrandLogo } from "@/components/brand-logo";
import { DevAuthBanner } from "@/components/dev-auth-banner";
import { CoreNavigation } from "@/components/core-navigation";
import { type AuthState, getAuthState } from "@/lib/auth";

interface AppShellProps {
  children: React.ReactNode;
  authState?: AuthState;
}

export function AppShell({ children, authState }: AppShellProps) {
  const auth = authState ?? getAuthState();

  return (
    <div className="min-h-screen bg-brand-background text-slate-950">
      {auth.mode === "mock" && auth.authenticated ? <DevAuthBanner /> : null}
      <div className="mx-auto flex min-h-[calc(100vh-33px)] max-w-[1440px] flex-col lg:flex-row">
        <aside className="border-b border-slate-200 bg-white/90 px-5 py-4 backdrop-blur lg:sticky lg:top-0 lg:h-screen lg:w-60 lg:self-start lg:overflow-y-auto lg:border-b-0 lg:border-r lg:px-5 lg:py-7">
          <div className="flex items-center justify-between gap-4 lg:block">
            <Link
              href="/dashboard"
              aria-label="Oryntela Home"
              className="inline-flex min-h-11 items-center rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
            >
              <BrandLogo
                className="size-10 sm:hidden"
                decorative
                variant="symbol"
              />
              <BrandLogo className="hidden h-8 w-auto sm:block" decorative />
            </Link>
            <div className="flex items-center gap-2 lg:mt-5">
              <span className="rounded-full border border-brand-secondary/15 bg-brand-secondary/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-brand-primary">
                Conversation intelligence
              </span>
              <Link
                href="/assistant"
                className="inline-flex min-h-10 items-center rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-focus lg:hidden"
              >
                Search
              </Link>
              <details className="relative lg:hidden">
                <summary className="inline-flex min-h-10 cursor-pointer list-none items-center rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-focus [&::-webkit-details-marker]:hidden">
                  Account
                </summary>
                <div className="absolute right-0 z-30 mt-2 w-64 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl">
                  <p className="px-2 pb-2 text-xs font-semibold text-slate-500">
                    {auth.organisation?.name ?? "No active organisation"}
                  </p>
                  {auth.mode === "clerk" ? (
                    <div className="border-b border-slate-100 px-2 pb-3">
                      <OrganizationSwitcher
                        hidePersonal
                        afterSelectOrganizationUrl="/onboarding"
                        afterCreateOrganizationUrl="/onboarding"
                      />
                    </div>
                  ) : null}
                  <Link
                    href="/settings"
                    className="mt-1 block rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-focus"
                  >
                    Settings
                  </Link>
                  <Link
                    href="/sign-out"
                    className="block rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-focus"
                  >
                    Sign out
                  </Link>
                </div>
              </details>
            </div>
          </div>
          <CoreNavigation />
          <div className="mt-5 hidden border-t border-slate-200 pt-5 lg:block">
            {auth.mode === "clerk" ? (
              <div className="mb-4">
                <OrganizationSwitcher
                  hidePersonal
                  afterSelectOrganizationUrl="/onboarding"
                  afterCreateOrganizationUrl="/onboarding"
                />
              </div>
            ) : null}
            <Link
              href="/sign-out"
              className="block rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-brand-secondary/10 hover:text-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
            >
              Sign out
            </Link>
          </div>
          <div className="mt-8 hidden border-t border-slate-200 px-3 pt-5 lg:block">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {auth.mode === "mock"
                ? "Development workspace"
                : "Private beta workspace"}
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-700">
              {auth.organisation?.name ?? "No active organisation"}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              {auth.mode === "mock"
                ? "Local mock identity. Never use production customer data here."
                : "Production customer data remains prohibited until separately approved."}
            </p>
          </div>
        </aside>
        <main className="min-w-0 flex-1 px-5 pb-28 pt-7 sm:px-8 lg:px-10 lg:py-9 xl:px-14">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
