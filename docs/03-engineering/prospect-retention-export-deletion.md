# Prospect retention, export and deletion

**Status:** Current WO-026 lifecycle

Prospect data follows the organisation’s configured private-beta retention period.
The retention job selects non-active Research Targets older than the cutoff and
deletes them with their runs, sources, observations and links. Targets with pending,
fetching or synthesising work are not removed. The implementation stores no fetched
page body, extraction cache, active HTML or raw provider response.

Organisation export schema version 16 adds separate `prospectTargets`,
`prospectRuns`, `prospectSources`, `prospectObservations` and
`prospectObservationSources` collections. The export includes identity, lifecycle,
trust and source metadata required to understand the research and promotion link.
It excludes provider credentials, raw provider payloads, full web pages and
temporary content.

Deleting an individual Research Target removes its complete research graph. A
linked canonical Company is not cascaded and survives. Organisation deletion counts
and removes the Prospect graph explicitly before tenant membership teardown; the
normal organisation-deletion lifecycle separately removes canonical Core entities.

Module entitlement and usage counters are tenant operational metadata. Entitlement
revocation blocks new reads/searches/runs and causes a claimed run to fail closed;
it does not silently destroy retained research. User removal similarly removes
access and prevents worker execution on the removed requester while organisation
retention remains authoritative.
