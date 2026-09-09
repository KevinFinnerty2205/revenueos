import Link from "next/link";
import { BrandLogo } from "@/components/brand-logo";

const currentOutcomes = [
  "Prepare from linked, validated account context",
  "Capture a bounded post-interaction debrief",
  "Add authorised visual evidence from the browser",
  "Review every AI-suggested claim before it updates intelligence",
] as const;

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-brand-background">
      <div className="mx-auto max-w-7xl px-5 py-6 sm:px-8 lg:px-12">
        <header className="flex items-center justify-between">
          <Link
            href="/"
            aria-label="Oryntela Home"
            className="inline-flex min-h-11 items-center rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
          >
            <BrandLogo
              className="size-10 sm:hidden"
              decorative
              variant="symbol"
            />
            <BrandLogo className="hidden h-9 w-auto sm:block" decorative />
          </Link>
          <nav
            aria-label="Account navigation"
            className="flex items-center gap-2 sm:gap-4"
          >
            <Link
              href="/sign-in"
              className="rounded-full px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-950 focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
            >
              Sign in
            </Link>
            <Link
              href="/sign-up"
              className="rounded-full bg-brand-primary px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
            >
              Create an account
            </Link>
          </nav>
        </header>

        <section className="relative grid gap-12 pb-24 pt-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:pb-36 lg:pt-32">
          <div className="relative z-10">
            <p className="inline-flex rounded-full border border-brand-secondary/25 bg-brand-secondary/10 px-4 py-2 text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
              Sales Brain · Private beta
            </p>
            <h1 className="mt-7 max-w-4xl text-5xl font-semibold leading-[1.04] tracking-[-0.04em] text-slate-950 sm:text-6xl lg:text-7xl">
              The AI sales teammate that remembers every customer interaction
              and turns conversations into action.
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-slate-600">
              Prepare for conversations, capture what changed, review the
              evidence and carry validated context into the next action.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link
                href="/sign-up"
                className="rounded-full bg-brand-primary px-6 py-3.5 text-sm font-bold text-white shadow-lg shadow-brand-primary/10 transition hover:bg-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
              >
                Open the private-beta workspace
              </Link>
              <Link
                href="/sign-in"
                className="rounded-full border border-slate-300 bg-white px-6 py-3.5 text-sm font-bold text-slate-800 transition hover:border-brand-secondary/50 hover:text-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
              >
                Sign in
              </Link>
            </div>
            <p className="mt-6 text-sm leading-6 text-slate-500">
              The current build supports deliberate transcripts, preparation
              briefs, reviewed debriefs and private reviewed visual evidence.
              Optional browser recording is consent-gated and never starts
              implicitly. Oryntela does not send changes to connected systems.
            </p>
          </div>

          <aside
            aria-labelledby="current-workspace-title"
            className="relative overflow-hidden rounded-[2rem] bg-brand-primary p-6 text-white shadow-2xl shadow-slate-900/10 sm:p-8"
          >
            <div className="absolute -right-20 -top-24 size-64 rounded-full bg-brand-accent/20 blur-3xl" />
            <div className="relative">
              <div className="flex items-center justify-between border-b border-white/10 pb-5">
                <h2
                  id="current-workspace-title"
                  className="text-sm font-bold uppercase tracking-[0.18em] text-brand-primary-foreground"
                >
                  Current workflow
                </h2>
                <span className="rounded-full bg-white/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-300">
                  Review required
                </span>
              </div>
              <ul className="mt-8 space-y-4">
                {currentOutcomes.map((outcome) => (
                  <li
                    key={outcome}
                    className="flex gap-3 text-sm leading-6 text-slate-300"
                  >
                    <span
                      aria-hidden="true"
                      className="mt-2 size-1.5 rounded-full bg-brand-accent"
                    />
                    {outcome}
                  </li>
                ))}
              </ul>
              <p className="mt-8 border-t border-white/10 pt-5 text-xs leading-5 text-slate-400">
                AI suggestions remain labelled and cannot update intelligence
                until a user completes review.
              </p>
            </div>
          </aside>
        </section>
      </div>
      <footer className="border-t border-slate-200 px-5 py-6 text-center text-xs text-slate-500 sm:px-8">
        Oryntela · Sales Brain private beta ·{" "}
        <a
          className="font-semibold text-brand-secondary underline decoration-1 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-focus"
          href="mailto:support@oryntela.com.au"
        >
          support@oryntela.com.au
        </a>
      </footer>
    </main>
  );
}
