import Link from "next/link";
import { DevAuthBanner } from "@/components/dev-auth-banner";
import { type AuthState, getAuthState } from "@/lib/auth";

const navigation = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/companies", label: "Companies" },
  { href: "/contacts", label: "Contacts" },
  { href: "/opportunities", label: "Opportunities" },
  { href: "/meetings", label: "Meetings" },
  { href: "/tasks", label: "Tasks" },
  { href: "/assistant", label: "Assistant" },
  { href: "/settings", label: "Settings" },
] as const;

interface AppShellProps {
  children: React.ReactNode;
  authState?: AuthState;
}

export function AppShell({ children, authState }: AppShellProps) {
  const auth = authState ?? getAuthState();

  return (
    <div className="min-h-screen bg-[#f5f7f4] text-slate-950">
      {auth.mode === "mock" && auth.authenticated ? <DevAuthBanner /> : null}
      <div className="mx-auto flex min-h-[calc(100vh-33px)] max-w-[1440px] flex-col lg:flex-row">
        <aside className="border-b border-slate-200 bg-white/80 px-5 py-5 lg:min-h-screen lg:w-64 lg:border-b-0 lg:border-r lg:px-6 lg:py-8">
          <div className="flex items-center justify-between gap-4 lg:block">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
            >
              <span className="grid size-9 place-items-center rounded-xl bg-teal-700 text-sm font-black text-white">
                R
              </span>
              <span className="text-lg font-bold tracking-tight">
                RevenueOS
              </span>
            </Link>
            <span className="rounded-full border border-slate-200 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500 lg:mt-5 lg:inline-block">
              Sales Brain
            </span>
          </div>
          <nav
            aria-label="Main navigation"
            className="mt-6 flex gap-2 overflow-x-auto pb-1 lg:mt-12 lg:block lg:space-y-1 lg:overflow-visible lg:pb-0"
          >
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="whitespace-nowrap rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-teal-50 hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 lg:block"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="mt-5 border-t border-slate-200 pt-5">
            <Link
              href="/sign-out"
              className="block rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-teal-50 hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
            >
              Sign out
            </Link>
          </div>
          <div className="mt-6 hidden rounded-2xl bg-slate-950 p-4 text-white lg:block">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-300">
              Development workspace
            </p>
            <p className="mt-2 text-sm font-semibold">
              {auth.organisation?.name ?? "No active organisation"}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              Local mock identity. Never use production customer data here.
            </p>
          </div>
        </aside>
        <main className="flex-1 px-5 py-8 sm:px-8 lg:px-12 lg:py-10">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
