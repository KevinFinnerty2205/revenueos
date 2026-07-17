import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

interface PlaceholderPageProps {
  eyebrow: string;
  title: string;
  description: string;
  emptyTitle: string;
  emptyDescription: string;
}

export function PlaceholderPage({
  eyebrow,
  title,
  description,
  emptyTitle,
  emptyDescription,
}: PlaceholderPageProps) {
  return (
    <>
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <EmptyState title={emptyTitle} description={emptyDescription} />
    </>
  );
}
