import Link from "next/link";
import { getAuthState } from "@/lib/auth";

export default function SignUpPage() {
  const auth = getAuthState();

  return (
    <main className="grid min-h-screen place-items-center bg-[#f5f7f4] px-5 py-12">
      <section
        className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-900/5 sm:p-10"
        aria-labelledby="sign-up-title"
      >
        <Link
          href="/"
          className="text-sm font-bold text-teal-800 hover:text-teal-950 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
        >
          ← Back to RevenueOS
        </Link>
        <p className="mt-10 text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
          Project foundation
        </p>
        <h1
          id="sign-up-title"
          className="mt-3 text-4xl font-semibold tracking-tight text-slate-950"
        >
          Create your workspace
        </h1>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          {auth.mode === "mock"
            ? "Local development uses a clearly marked example organisation. It does not create a real account."
            : "Clerk will own account and organisation creation. That hosted flow is not connected in Sprint 1."}
        </p>
        {auth.authenticated ? (
          <Link
            href="/dashboard"
            className="mt-8 block rounded-full bg-teal-700 px-5 py-3 text-center text-sm font-bold text-white hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
          >
            Open example workspace
          </Link>
        ) : (
          <p
            role="status"
            className="mt-8 rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-950"
          >
            {auth.message}
          </p>
        )}
      </section>
    </main>
  );
}
