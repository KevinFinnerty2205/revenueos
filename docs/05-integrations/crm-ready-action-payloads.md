# CRM-ready Action payloads

Action payloads preserve proposed intent without applying it. Opportunity updates
name one allowed field, current value, proposed value and reason. Contact and
stakeholder proposals identify the target and proposed bounded values. Task proposals
include title, owner, due date, context and linked Opportunity/Interaction. Timeline,
procurement and security/legal proposals preserve current/proposed values and reason.

These contracts make later mapping testable while avoiding today’s vendor-specific
objects. They contain no provider account ID, access token, remote record ID or sync
state. RevenueOS does not claim a CRM integration until a separately approved adapter
performs authenticated tenant-scoped writes and records provider confirmation.
