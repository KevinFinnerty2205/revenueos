import Link from "next/link";
import { SignUp } from "@clerk/nextjs";
import { BrandLogo } from "@/components/brand-logo";
import { getAuthState } from "@/lib/auth";

export default function SignUpPage() {
  const auth = getAuthState();
  const clerkConfigured =
    auth.mode === "clerk" &&
    Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

  if (clerkConfigured) {
    return (
      <main className="grid min-h-screen place-items-center bg-brand-background px-5 py-12">
        <div className="grid justify-items-center gap-8">
          <BrandLogo className="h-10 w-auto" />
          <SignUp
            path="/sign-up"
            signInUrl="/sign-in"
            forceRedirectUrl="/select-organisation"
          />
        </div>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-brand-background px-5 py-12">
      <section
        className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-900/5 sm:p-10"
        aria-labelledby="sign-up-title"
      >
        <BrandLogo className="h-9 w-auto" />
        <Link
          href="/"
          className="mt-8 inline-flex text-sm font-bold text-brand-secondary hover:text-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
        >
          ← Back to Oryntela
        </Link>
        <p className="mt-10 text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
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
            : "Clerk account creation is not configured for this environment."}
        </p>
        {auth.authenticated ? (
          <Link
            href="/dashboard"
            className="mt-8 block rounded-full bg-brand-primary px-5 py-3 text-center text-sm font-bold text-white hover:bg-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2"
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
