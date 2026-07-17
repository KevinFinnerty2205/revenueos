import { MeetingForm } from "@/components/meeting-form";

export default async function EditMeetingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MeetingForm meetingId={id} />;
}
