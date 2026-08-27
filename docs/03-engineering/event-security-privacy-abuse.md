# Event security, privacy, retention and abuse review

## Threats and controls

| Threat | Control |
| --- | --- |
| Unauthorised attendee list | required versioned attestation with user/timestamp; no claim of marketing consent |
| Overcollection | allowlisted mapping; sensitive headers un-mappable; bounded cells |
| Parser/formula abuse | strict UTF-8 CSV, byte/row/column limits, null rejection, formula text only |
| False identity merge | exact strong identifiers only; generic inbox/name-only cannot auto-link |
| Cross-tenant access | composite tenant FKs, repository predicates and forced PostgreSQL RLS |
| Bulk harvesting/sending | 500-attendee/Event and import limits; explicit single promotion; canonical Contact-only Campaign cap |
| Deceptive follow-up | met claim requires encounter/Interaction; conversation claims retain provenance |
| Attendance-to-permission shortcut | Event trust remains distinct; WO-029 policy/suppression/contactability revalidate |
| Attendance-as-intent | no Evidence, Methodology, Buying Signal, score or Revenue Brain write |
| PII leakage | no raw CSV/file path/content logging; metadata-only telemetry and safe errors |

Metadata telemetry records organisation/Event/import/attendee identifiers, counts,
state, source type and whether an Interaction was created. It does not record names,
emails, company, title, notes, CSV rows, filenames or outreach content.

## Retention, export and deletion

Preview approved rows expire after one hour and are cleared; raw bytes are never
persisted. Confirmed Event-local attendee data follows
the organisation's existing private-beta retention period (default 90 days). The
maintenance pass deletes ended non-draft Event graphs older than the cutoff after
detaching preserved Interactions.

Organisation privacy export schema v21 includes Event metadata, approved attendee
fields, import provenance/attestation metadata, plans, encounters and linked IDs. It
excludes raw upload bytes, preview rows, file fingerprints, credentials, internal
paths, provider payloads and outreach content outside its existing authorised export.

Explicit Event deletion reports preserved Contact/Interaction/Campaign counts and
removes Event imports, attendees, states, encounters and links. Promoted canonical
records survive. Organisation deletion removes the Event graph in FK-safe order.

## Rollout and operations

`ENGAGE_EVENTS_ENABLED` is server-authoritative. Production must keep it disabled
until privacy/security review, target-environment migration/RLS evidence and rollout
approval complete. Engage loss permits read-only retained history/export, not new
imports or mutation. Operational checks cover import-limit errors, expired preview
cleanup and retention counts without inspecting attendee content.
