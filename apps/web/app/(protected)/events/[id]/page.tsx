import { EventDetailWorkspace } from "@/components/event-workspace";

export default async function EventPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EventDetailWorkspace eventId={id} />;
}
