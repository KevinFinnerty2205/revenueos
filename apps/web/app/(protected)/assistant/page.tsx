import { CoreSearch } from "@/components/core-search";
import { PageHeader } from "@/components/page-header";

export default async function AssistantPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const parameters = await searchParams;
  const scopeType =
    parameters.scope === "opportunity" || parameters.scope === "account"
      ? parameters.scope
      : "workspace";
  const scopeId =
    typeof parameters.scopeId === "string" ? parameters.scopeId : null;
  const question =
    typeof parameters.question === "string" ? parameters.question : "";
  const initialMode = parameters.mode === "ask" ? "ask" : "search";
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workspace"
        title="Search or ask RevenueOS"
        description="Find a record quickly, or ask a grounded question about what RevenueOS already knows."
      />
      <CoreSearch
        initialMode={initialMode}
        scopeType={scopeType}
        scopeId={scopeId}
        initialQuestion={question}
      />
    </div>
  );
}
