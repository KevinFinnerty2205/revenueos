"use client";

import Link from "next/link";

export default function ProtectedWorkspaceError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <section className="form-card" aria-labelledby="workspace-error-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-rose-700">
        RevenueOS workspace
      </p>
      <h1 id="workspace-error-title" className="mt-2 text-2xl font-semibold">
        This page could not be loaded
      </h1>
      <p role="alert" className="mt-3 max-w-2xl text-sm text-slate-700">
        Your work has not been changed. Try loading this page again, or return
        Home and continue from there.
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <button type="button" className="primary-button" onClick={reset}>
          Try again
        </button>
        <Link href="/dashboard" className="secondary-button">
          Return Home
        </Link>
      </div>
    </section>
  );
}
