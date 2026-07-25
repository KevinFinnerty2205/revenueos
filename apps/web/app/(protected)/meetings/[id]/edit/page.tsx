import { MeetingForm } from "@/components/meeting-form";
import { DataNoticeCard } from "@/components/data-notice-card";

export default async function EditMeetingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <DataNoticeCard />
      <MeetingForm meetingId={id} />
    </div>
  );
}
