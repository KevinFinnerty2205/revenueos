import type {
  InteractionLifecycleStatus,
  InteractionType,
} from "@revenueos/shared";

export const interactionTypes: InteractionType[] = [
  "online_meeting",
  "face_to_face_meeting",
  "presentation",
  "workshop",
  "site_visit",
  "executive_lunch",
  "phone_call",
  "conference_interaction",
  "trade_show_interaction",
  "manual_interaction",
];

export const interactionStatuses: InteractionLifecycleStatus[] = [
  "planned",
  "in_progress",
  "completed",
  "cancelled",
];

export function formatInteractionDate(value: string | null): string {
  if (!value) return "Time not set";
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
