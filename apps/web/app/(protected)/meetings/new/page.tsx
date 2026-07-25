import { MeetingForm } from "@/components/meeting-form";
import { DataNoticeCard } from "@/components/data-notice-card";

export default function NewMeetingPage() {
  return (
    <div className="space-y-6">
      <DataNoticeCard />
      <MeetingForm />
    </div>
  );
}
