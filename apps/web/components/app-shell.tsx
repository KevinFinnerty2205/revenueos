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
        <aside className="border-b border-slate-200 bg-white/80 px-5 py-4 lg:min-h-screen lg:w-64 lg:border-b-0 lg:border-r lg:px-6 lg:py-8">
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
            <span className="rounded-full border border-slate-200 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500 lg:mt-5 lg:inline-block">
              Sales Brain
            </span>
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
          <div className="mt-6 hidden rounded-2xl bg-brand-primary p-4 text-white lg:block">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-primary-foreground">
              {auth.mode === "mock"
                ? "Development workspace"
                : "Private beta workspace"}
            </p>
            <p className="mt-2 text-sm font-semibold">
              {auth.organisation?.name ?? "No active organisation"}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              {auth.mode === "mock"
                ? "Local mock identity. Never use production customer data here."
                : "Production customer data remains prohibited until separately approved."}
            </p>
          </div>
        </aside>
        <main className="min-w-0 flex-1 px-5 pb-28 pt-7 sm:px-8 lg:px-12 lg:py-10">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
