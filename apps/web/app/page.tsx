import Link from "next/link";

const currentOutcomes = [
  "Prepare from linked, validated account context",
  "Capture a bounded post-interaction debrief",
  "Add authorised visual evidence from the browser",
  "Review every AI-suggested claim before it updates intelligence",
] as const;

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#f5f7f4]">
      <div className="mx-auto max-w-7xl px-5 py-6 sm:px-8 lg:px-12">
        <header className="flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
          >
            <span className="grid size-9 place-items-center rounded-xl bg-teal-700 text-sm font-black text-white">
              R
            </span>
            <span className="text-lg font-bold tracking-tight text-slate-950">
              RevenueOS
            </span>
          </Link>
          <nav
            aria-label="Account navigation"
            className="flex items-center gap-2 sm:gap-4"
          >
            <Link
              href="/sign-in"
              className="rounded-full px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-950 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
            >
              Sign in
            </Link>
            <Link
              href="/sign-up"
              className="rounded-full bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
            >
              Create an account
            </Link>
          </nav>
        </header>

        <section className="relative grid gap-12 pb-24 pt-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:pb-36 lg:pt-32">
          <div className="relative z-10">
            <p className="inline-flex rounded-full border border-teal-200 bg-teal-50 px-4 py-2 text-xs font-bold uppercase tracking-[0.18em] text-teal-800">
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
                className="rounded-full bg-teal-700 px-6 py-3.5 text-sm font-bold text-white shadow-lg shadow-teal-900/10 transition hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
              >
                Open the private-beta workspace
              </Link>
              <Link
                href="/sign-in"
                className="rounded-full border border-slate-300 bg-white px-6 py-3.5 text-sm font-bold text-slate-800 transition hover:border-teal-400 hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
              >
                Sign in
              </Link>
            </div>
            <p className="mt-6 text-sm leading-6 text-slate-500">
              The current build supports deliberate transcripts, preparation
              briefs, reviewed debriefs and private reviewed visual evidence.
              Optional browser recording is consent-gated and never starts
              implicitly. RevenueOS does not send changes to connected systems.
            </p>
          </div>

          <aside
            aria-labelledby="current-workspace-title"
            className="relative overflow-hidden rounded-[2rem] bg-slate-950 p-6 text-white shadow-2xl shadow-slate-900/10 sm:p-8"
          >
            <div className="absolute -right-20 -top-24 size-64 rounded-full bg-teal-400/20 blur-3xl" />
            <div className="relative">
              <div className="flex items-center justify-between border-b border-white/10 pb-5">
                <h2
                  id="current-workspace-title"
                  className="text-sm font-bold uppercase tracking-[0.18em] text-teal-300"
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
                      className="mt-2 size-1.5 rounded-full bg-teal-300"
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
        RevenueOS AI · Sales Brain private beta
      </footer>
    </main>
  );
}
