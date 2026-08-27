# ADR 0047: Separate Event attendee, encounter and contactability boundaries

## Context

An authorised Event list can help a seller find relevant people, but it is neither a
canonical CRM record nor evidence of a customer conversation, outreach permission or
buying intent. Automatically promoting or scoring every attendee would contaminate
relationship truth and create a bulk-marketing bypass.

## Decision

Store an EventAttendee as a retained Event-local identity with exact-source fields and
conservative matches. Promotion to Company/Contact is explicit and records
`event_list` field provenance; it never creates an Opportunity. Store a per-user
EventEncounter for mark-met and bounded seller notes. Only deliberate capture creates
an optional Event-linked Interaction; mark-met alone creates no Evidence.

Attendance remains separate from contactability and Revenue Brain truth. Outreach and
Campaigns require a canonical Contact and reuse every WO-029/WO-030 policy,
suppression, approval and execution control. Priority is categorical and explainable,
with no numeric lead/intent score.

## Alternatives

- **Import every attendee as a Contact:** rejected as overcollection and duplicate risk.
- **Treat every attendee as a Prospect lead:** rejected because Prospect is optional
  and attendance is not public research or intent.
- **Create an Interaction on mark-met:** rejected because a tap does not prove a
  customer conversation.
- **Send directly to raw Event email:** rejected because it bypasses canonical trust,
  suppression and audience review.

## Consequences

The Event flow needs explicit promotion before sending and some matches require human
review. In return, canonical sales history remains clean, truth provenance is
auditable, Engage safety is not weakened and Event deletion can remove local attendee
data while preserving reviewed Contacts, Interactions and Campaign history.
