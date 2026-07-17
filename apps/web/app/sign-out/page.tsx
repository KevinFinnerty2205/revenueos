import Link from "next/link";
import { getAuthState } from "@/lib/auth";

export default function SignOutPage() {
  const auth = getAuthState();

  return (
    <main className="grid min-h-screen place-items-center bg-[#f5f7f4] px-5 py-12">
      <section
        className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-xl shadow-slate-900/5 sm:p-10"
        aria-labelledby="sign-out-title"
      >
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
          Authentication
        </p>
        <h1
          id="sign-out-title"
          className="mt-3 text-4xl font-semibold tracking-tight text-slate-950"
        >
          Sign out
        </h1>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          {auth.mode === "mock"
            ? "Development authentication does not create a persistent session. Closing the local application ends your work."
            : "Clerk session termination will be connected when production authentication is implemented."}
        </p>
        <Link
          href="/"
          className="mt-8 inline-flex rounded-full bg-slate-950 px-5 py-3 text-sm font-bold text-white hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
        >
          Return to RevenueOS
        </Link>
      </section>
    </main>
  );
}
