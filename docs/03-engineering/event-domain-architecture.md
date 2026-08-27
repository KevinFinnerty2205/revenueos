# Event domain architecture

## Boundary

WO-031 adds Event context to the existing modular monolith. Engage owns Event create,
import, planning and outreach. Prospect is optional enrichment and Core owns canonical
Company, Contact, Opportunity, Interaction and Evidence. No worker, queue, provider or
new datastore is introduced.

Migration `0040_event_intelligence` creates six forced-RLS tenant tables:

- `sales_events`: manual Event metadata, goal, owner and lifecycle;
- `event_attendee_imports`: bounded preview/import metadata, mapping, temporary
  approved preview rows and authority attestation;
- `event_attendees`: approved Event-list fields plus conservative links and priority;
- `event_attendee_user_states`: per-user planned/met/follow-up state;
- `event_encounters`: seller-reported met/outcome/note and optional Interaction link;
- `event_campaign_links`: Event-to-existing Campaign association.

`interactions.event_id` is nullable. Event deletion first detaches this reference, then
cascades Event-local rows. Canonical Contact, Company, Opportunity, Interaction,
Outreach and Campaign records are never cascade-deleted by the Event.

All relationships use organisation-scoped foreign keys and repositories include an
explicit organisation predicate. PostgreSQL enables and forces RLS on every new
table using the trusted transaction-local organisation setting.

## Lifecycle and state

Stored Event states are draft/upcoming/active/completed/archived. Active/completed are
derived from UTC timestamps at read time unless archived, so no transition worker is
required. End must not precede start and duration is at most 30 days. Event type is a
closed business taxonomy and location/organiser are bounded text; HTTPS Event URLs
are validated but never fetched.

## Read models and performance

List summary, Event Campaign links, attendee state/encounter expansion, Contact/email,
Company/domain, Prospect/profile, Opportunity and Target Market matching use bounded
set queries. Attendee reads are server-paginated and searchable. The 500-attendee cap
keeps synchronous CSV preview/confirmation bounded. No automatic provider fan-out or
N+1 attendee matching is performed.

## API

The `/api/v1/engage/events` surface provides list/create/get/patch/delete, preview/get
preview/confirm import, paginated attendees, per-user plan, encounter, promotion and
Event outreach. FastAPI/Pydantic remains the source of truth and shared TypeScript
contracts mirror the customer-facing response shape.
