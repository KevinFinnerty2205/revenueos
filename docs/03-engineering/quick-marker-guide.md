# Quick marker guide

## Purpose

Quick markers help a user return to an important moment without typing during a
conversation. They are navigation and debrief metadata, not evidence, notes,
intelligence or customer facts.

Supported types are buying signal, objection, decision, action item, risk,
stakeholder, timeline, budget, procurement, follow-up, important moment,
customer question, requested material and strong engagement.

Each marker stores:

- organisation and Interaction scope;
- controlled marker type;
- creating user;
- UTC creation time;
- optional recording offset in milliseconds; and
- an internal idempotency key that is never exported.

There is no free-text field. Marker contents must not be placed in logs or audit
metadata. A marker can influence which bounded debrief target is asked next, but
it cannot update Interaction Intelligence, an Opportunity or Revenue Brain by
itself.

## API

- `POST /api/v1/interactions/{id}/companion/markers`
- `GET /api/v1/interactions/{id}/companion/markers`
- `DELETE /api/v1/interactions/{id}/companion/markers/{markerId}`

All repository predicates include organisation scope. PostgreSQL RLS is forced
on `interaction_markers`. Migration `0026_face_to_face_companion` adds a database
trigger that rejects metadata mutation and undelete. Soft deletion is available
only before Interaction completion. Markers participate in organisation export,
deletion and retention through the owning Interaction.
