import Link from "next/link";
import { BrandLogo } from "@/components/brand-logo";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center bg-brand-background px-5 py-12">
      <section className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-xl shadow-slate-900/5 sm:p-12">
        <BrandLogo className="mx-auto h-10 w-auto" />
        <p className="mt-10 text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
          Page not found
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
          This page is not available
        </h1>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          The address may be incorrect, or the page may have moved. You can
          return to Oryntela or contact us if you need a hand.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link className="primary-button" href="/">
            Return home
          </Link>
          <Link className="secondary-button" href="/contact">
            Contact Oryntela
          </Link>
        </div>
      </section>
    </main>
  );
}
