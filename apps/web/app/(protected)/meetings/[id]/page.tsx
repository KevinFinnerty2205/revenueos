import { MeetingDetail } from "@/components/meeting-detail";
import { DataNoticeCard } from "@/components/data-notice-card";

export default async function MeetingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <DataNoticeCard />
      <MeetingDetail meetingId={id} />
    </div>
  );
}
