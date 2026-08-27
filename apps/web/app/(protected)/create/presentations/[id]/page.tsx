import { CreatePresentationReview } from "@/components/create-presentation-review";

export default async function CreatePresentationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CreatePresentationReview presentationId={id} />;
}
