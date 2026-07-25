import { RevenueBrainTimeline } from "@/components/revenue-brain-timeline";

export default async function CompanyAccountPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RevenueBrainTimeline accountId={id} />;
}
