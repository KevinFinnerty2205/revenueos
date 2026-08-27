# Events — implementation guide

- **Status:** implemented by WO-031 behind the Engage Events feature and entitlement
- **Purpose:** help a relationship seller prepare for, work through and follow up a
  business Event without becoming an event-management or lead-harvesting platform

## Customer workflow

Before an Event, a seller creates a bounded workspace, deliberately selects an
authorised UTF-8 CSV, maps approved business fields, reviews exclusions and accepts
the versioned authority statement. RevenueOS conservatively links exact identities,
surfaces existing relationships and active Opportunities, and assigns an explainable
category: **Priority to meet**, **Worth meeting**, **Context only** or **Needs more
information**. There is no numeric score and attendance is not intent.

During an Event, the responsive People view supports search, plan/unplan, a large
**Mark met** control, a bounded seller note, **Follow up later**, explicit **Add to
Sales**, and handoff to the existing face-to-face Companion. Marking met creates an
EventEncounter only: it does not create customer Evidence, Opportunity, Methodology
state, Buying Signal or Revenue Brain truth.

After an Event, the follow-up view shows seller-reported encounters and plans.
One-to-one drafts reuse WO-029 and an explicitly selected audience of canonical
Contacts can hand off to WO-030. Nothing sends automatically.

## Attendee trust and contactability

An EventAttendee is Event-local authorised-list data, not a Contact. Approved fields
are name, company, role, business email, country/location, professional profile URL,
company domain and registration category. Health, dietary, disability, home address,
private phone and similar registration fields are ignored and cannot be mapped.

An imported email is `provider_supplied`, never verified. Shared role inboxes may be
displayed but are not strong person identities. Exact business email/profile matching
is allowed; exact company domain may link company context; name-only similarity is
only a possible match. No fuzzy merge occurs.

The import attestation means authority to use the list for the stated business
purpose. It is not consent to email. Outreach always requires an explicit canonical
Contact and the current Engage policy, source trust, suppression, cooldown and quota
checks. Event attendance cannot bypass those controls.

## Sales Brain handoff

**Add to Sales** is an explicit review action. It links an exact Contact or creates a
reviewed Company/Contact with `event_list` field provenance; it never creates an
Opportunity. Existing Contacts are not overwritten. Once promoted, the Contact is
the recipient boundary for outreach and Campaigns.

An EventEncounter may remain attached to an unpromoted attendee. Full capture creates
a planned or completed Event-linked Interaction and can open the existing Companion.
Any later debrief/recording follows the existing origin and review rules. Seller notes
remain `seller_reported_activity`; they are not silently upgraded to customer-direct
Evidence.

Prospect is an optional enhancement. If entitled, the seller may explicitly open the
existing Find/research path. RevenueOS does not research all attendees or overwrite
Event-list facts with public research.

## Current limits and known limitations

- CSV only; 5 MB, 50 columns and 500 rows/attendees per Event.
- Five confirmed imports per Event per UTC day and 50 active/upcoming Events per
  organisation; previews expire after one hour.
- Manual Event creation and selected-file import only; no Eventbrite/Cvent/Swapcard
  connector, XLSX, ticketing, registration, badge scanning, OCR or facial matching.
- No bulk Contact/Opportunity creation, “email all attendees”, lead score, attendance
  buying signal, automatic attendee research, open/click tracking, calendar booking or
  reply detection.
- Real email remains subject to the separately approved mailbox availability; normal
  tests use deterministic mocks and make no external provider/email calls.

Disabling Engage makes retained Event history read-only and exportable while blocking
new imports, mutation and outreach. Event deletion removes Event-local rows but
preserves promoted Contacts/Companies, Interactions and Campaign history after links
are detached.
