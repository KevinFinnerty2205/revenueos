import { auth } from "@clerk/nextjs/server";
import { CreateOrganization, OrganizationList } from "@clerk/nextjs";
import { redirect } from "next/navigation";
import { getAuthState } from "@/lib/auth";

export default async function SelectOrganisationPage() {
  const configured = getAuthState();
  if (configured.mode === "mock") redirect("/dashboard");
  const session = await auth();
  if (!session.userId) redirect("/sign-in");
  if (session.orgId) redirect("/onboarding");

  return (
    <main className="min-h-screen bg-[#f5f7f4] px-5 py-12">
      <div className="mx-auto grid max-w-4xl gap-8 lg:grid-cols-2">
        <section className="form-card" aria-labelledby="organisation-title">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Private beta
          </p>
          <h1
            id="organisation-title"
            className="mt-3 text-3xl font-semibold text-slate-950"
          >
            Select your organisation
          </h1>
          <p className="mt-4 text-sm leading-7 text-slate-600">
            RevenueOS keeps every meeting and insight inside the active
            organisation. Choose an invitation or create the workspace approved
            for your beta trial.
          </p>
          <div className="mt-6">
            <OrganizationList
              hidePersonal
              afterSelectOrganizationUrl="/onboarding"
            />
          </div>
        </section>
        <section
          className="form-card"
          aria-labelledby="create-organisation-title"
        >
          <h2
            id="create-organisation-title"
            className="text-2xl font-semibold text-slate-950"
          >
            Create an approved workspace
          </h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Only create an organisation when your RevenueOS beta operator has
            approved it.
          </p>
          <div className="mt-6">
            <CreateOrganization
              skipInvitationScreen
              afterCreateOrganizationUrl="/onboarding"
            />
          </div>
        </section>
      </div>
    </main>
  );
}
