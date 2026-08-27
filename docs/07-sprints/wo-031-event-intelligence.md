# WO-031 — Event Intelligence

- **Branch:** `feature/epic-13-wo-031-event-intelligence`
- **Status:** implemented for draft PR; not merged
- **Migration:** `0040_event_intelligence`
- **Boundary:** manual business Events and authorised CSV attendee context under Engage

## Outcome

WO-031 adds the smallest before/during/after Event workflow: create an Event, preview
and attest a bounded attendee import, understand exact relationships and explainable
priority, plan people, mark encounters, explicitly promote Contacts, open the existing
Companion, and prepare truthful WO-029/WO-030 follow-up.

The implementation adds six forced-RLS Event tables, nullable Interaction linkage,
tenant-scoped repositories/services/routes, shared contracts, retention/export v21,
Sell navigation, a four-tab responsive Event workspace and a deterministic Daily
active-Event card. CSV is strict UTF-8 only, raw bytes are never retained, previews
expire after one hour and all imports/promotion/sending boundaries fail closed.

## Product and truth boundaries

EventAttendee is separate from Contact. Exact strong email/profile and company-domain
matches are set-based; shared mailboxes and names cannot silently merge people.
Priority is categorical with reasons and no score. Prospect research is optional and
explicit. An EventEncounter/seller note is seller-reported activity; mark-met creates
no Evidence. Attendance does not imply permission, Buying Signal, Methodology state or
Revenue Brain truth. Raw attendees cannot enter outreach/Campaign execution.

No ticketing, registration, payment, agenda, Event-platform integration, badge/OCR,
facial recognition, automatic research, automatic Contact/Opportunity creation,
mass-attendee email, open/click tracking, reply detection or real provider call was
added.

## Verification

The implementation includes parser, CRUD, matching, priority, plan, encounter,
promotion, outreach truthfulness, Campaign link, entitlement, deletion, export,
migration, RLS/cross-tenant, component and Playwright coverage. The complete local
gate passed with 184 web tests, 927 API tests (four intentionally skipped in the
ordinary SQLite run), 46 Playwright journeys and two explicit PostgreSQL RLS tests.
Format, lint, strict type-checking, production builds, Alembic upgrade/autogenerate
check and the repository audit also passed.

Reviewed visual evidence:

- [desktop first-use Event list](images/wo-031/events-first-use-desktop.png)
- [desktop Event People workspace](images/wo-031/event-people-desktop.png)
- [mobile mark-met truth state](images/wo-031/event-day-mobile-met.png)

## Rollback

Disable `API_FEATURE_ENGAGE_EVENTS_ENABLED` to make the Event surface unavailable;
disable the organisation's Engage entitlement when retained read-only history is the
required downgrade experience. Application and migration may be rolled back together to `0039_campaign_sequences`
only after accepting deletion of Event-local records; the downgrade first normalises
Event-specific source values and preserves canonical sales history outside the Event
tables.
