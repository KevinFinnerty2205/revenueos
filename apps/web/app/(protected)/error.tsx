"use client";

interface ProtectedErrorProps {
  reset: () => void;
}

export default function ProtectedError({ reset }: ProtectedErrorProps) {
  return (
    <section
      role="alert"
      className="rounded-3xl border border-red-200 bg-white p-8 shadow-sm"
      aria-labelledby="workspace-error-title"
    >
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-red-700">
        Workspace error
      </p>
      <h1
        id="workspace-error-title"
        className="mt-3 text-3xl font-semibold text-slate-950"
      >
        This page could not be loaded.
      </h1>
      <p className="mt-3 max-w-xl text-sm leading-7 text-slate-600">
        Try again. If the problem continues, check the local web and API logs
        using the request identifier where available.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-6 rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
      >
        Try again
      </button>
    </section>
  );
}
