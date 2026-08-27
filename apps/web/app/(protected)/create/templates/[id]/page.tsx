import { CreateTemplateReview } from "@/components/create-template-review";

export default async function CreateTemplatePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CreateTemplateReview templateId={id} />;
}
