# Online Meeting provider adapter

**Status:** Provider-neutral boundary and deterministic fake implemented; no real
meeting-platform connection is configured.

`OnlineMeetingProviderAdapter` isolates provider behaviour from Interaction policy.
It validates and normalises meeting references, reports a provider meeting ID and
event times, lists authorised artefacts, retrieves typed recording/transcript
references and maps participants conservatively. It returns normalised metadata;
provider payloads, download URLs and credentials never enter business models or
logs.

The domain service remains responsible for tenant authorisation, organisation
settings, consent, size/quota checks, idempotency, duplicate detection, provenance,
retention and downstream orchestration. A connector may never trust an organisation
ID in a provider payload. Tokens are server-only and per organisation, use the
narrowest approved scopes, support revocation/re-authentication and are excluded
from audit records.

The deterministic fake covers validation, metadata normalisation, artifact listing
and retrieval, no-artifact and typed failure behaviour without network calls. It is
test infrastructure, not a working integration.

## Native adapter gates

Before a real adapter may set `native_fetch=true`, it needs sandbox contract tests,
least-privilege scope approval, entitlement testing, per-organisation connection
state, idempotent retrieval, bounded retry, expired/revoked-token handling and a
support runbook. If webhooks become necessary they additionally require signature
verification, replay protection, timestamp tolerance, event allowlisting, bounded
payloads and trusted tenant mapping. Auto-ingestion remains server-authoritative and
off by default; RevenueOS never silently processes every calendar meeting.

## First integration recommendation

No production connector is justified until the first design-partner ecosystem is
known. Google Meet v2 is the recommended first technical spike if pilot demand is
otherwise equal because it exposes purpose-built conference-record and artefact
resources with narrow read-only scopes. This is a spike recommendation, not a
claim that all Google Workspace plans expose recordings or transcripts. Teams may
be the correct first production choice for a Microsoft-heavy cohort; Zoom may be
correct where cloud recordings are the primary evidence source.
