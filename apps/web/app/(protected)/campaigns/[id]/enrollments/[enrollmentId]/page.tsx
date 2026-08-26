import { CampaignEnrollmentDetail } from "@/components/campaign-workspace";

export default async function CampaignEnrollmentPage({
  params,
}: {
  params: Promise<{ id: string; enrollmentId: string }>;
}) {
  const { id, enrollmentId } = await params;
  return (
    <CampaignEnrollmentDetail campaignId={id} enrollmentId={enrollmentId} />
  );
}
