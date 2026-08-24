import { CoreSearch } from "@/components/core-search";
import { PageHeader } from "@/components/page-header";

export default function AssistantPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workspace"
        title="Search"
        description="Go straight to the account, opportunity or interaction you need."
      />
      <CoreSearch />
    </div>
  );
}
