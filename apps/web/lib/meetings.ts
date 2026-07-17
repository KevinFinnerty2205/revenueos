import type {
  AttendanceStatus,
  MeetingStatus,
  MeetingType,
  ParticipantRole,
} from "@revenueos/shared";

export interface MeetingParticipantDraft {
  id?: string;
  contactId: string;
  displayName: string;
  email: string;
  attendanceStatus: AttendanceStatus;
  role: ParticipantRole;
}

export const meetingTypes: MeetingType[] = [
  "remote",
  "phone",
  "in_person",
  "other",
];

export const meetingStatuses: MeetingStatus[] = [
  "scheduled",
  "completed",
  "cancelled",
];

export const attendanceStatuses: AttendanceStatus[] = [
  "invited",
  "attended",
  "absent",
  "unknown",
];

export const participantRoles: ParticipantRole[] = ["host", "attendee"];

export function formatMeetingDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function toLocalDateTime(value: string): string {
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function emptyParticipant(): MeetingParticipantDraft {
  return {
    contactId: "",
    displayName: "",
    email: "",
    attendanceStatus: "invited",
    role: "attendee",
  };
}
