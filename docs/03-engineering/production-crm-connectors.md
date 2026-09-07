# Production CRM connectors

**Implementation:** WO-042, migration `0058_production_crm_connectors`
**Research reviewed:** 6 September 2026
**Runtime status:** HubSpot and Salesforce are production-capable, disabled by
default and not production-active. Native Oryntela CRM remains available without an
external CRM.

## Boundary and flow

Oryntela retains one canonical Company/Contact/Opportunity model for native and
externally connected customers. An external CRM is a source and optional reviewed
execution destination, not a second reporting universe.

`admin OAuth → encrypted tenant-bound connection → read-only background import →
owner/stage/field review → optional writeback enablement → per-record preview and
confirmation → immutable receipt`

The provider-neutral adapter emits only:

- allow-listed Account, Contact and Opportunity fields;
- provider object ID, version/modified time and archive state;
- bounded owner, account relationship and stage references; and
- opaque page cursor/high-watermark information used only by the server.

Raw provider responses, arbitrary custom properties, Notes, files, tasks, activities,
emails and calendar records do not cross this contract. The existing narrowly scoped
HubSpot meeting-log Action remains supported; broad CRM activity and task sync are
**deferred** to avoid duplicating Microsoft/Google and Oryntela Interaction context.

## Persistence and tenant isolation

`CRMEntityMapping` remains the provider/canonical binding and now retains external
version, authority version and archive state. WO-042 adds:

| Record | Purpose |
| --- | --- |
| `CRMConnectionState` | lifecycle, kill switch, health, mapping version and aggregate progress |
| `CRMOwnerMapping` | explicit provider-owner to active Oryntela-member decision |
| `CRMSyncCursor` | one durable full/incremental checkpoint per object |
| `CRMSyncJob` | bounded initial, incremental or reconcile work and lease/retry state |
| `CRMSyncReceipt` | immutable idempotency/provenance result without customer values |
| `CRMConflict` | current local/provider fingerprints and explicit resolution history |
| `CRMWritebackPreview` | short-lived exact write intent and confirmation fingerprint |

Every row is organisation-scoped, every relationship is tenant-consistent and every
repository query includes the organisation predicate. PostgreSQL enables and forces
RLS on all seven tables. Worker discovery uses narrow `SECURITY DEFINER` identifier-
only functions, then re-enters transaction-local tenant context before reading or
writing. The database also enforces one non-revoked HubSpot-or-Salesforce connection
per organisation and prevents the same provider tenant being attached to unrelated
Oryntela organisations.

Receipts cannot be updated. PostgreSQL deletion requires the explicit
`app.beta_maintenance=approved` transaction setting used by governed organisation
erasure; ordinary SQLite test/development deletion remains possible for deterministic
cleanup. Export version 35 includes bounded connection/mapping/receipt/conflict
provenance but excludes credentials, authorisation state secrets, provider bodies and
sync cursor tokens.

## Synchronisation lifecycle

OAuth creates a verified connection, sensible standard-field defaults and an initial
read-only job. The administrator-facing screen explains that only Companies,
Contacts and Opportunities are synchronised. Writeback remains off.

The worker handles one provider page for each eligible organisation per pass. The
default page is 100 records (hard maximum 200), each provider response is capped at
1 MB and retries are at most three with bounded delay. A committed cursor contains
the next provider page plus the highest observation in that run. The previous
high-watermark filter remains stable across every page and advances only when the
object pass completes, so pagination cannot skip records by changing its filter
mid-run. A crash resumes without returning to record one. The receipt key combines
connection, provider object and external version; seeing one provider revision
repeatedly produces one logical effect.

After initial completion, an interval-bucketed scheduler queues incremental work every
five minutes by default. HubSpot filters on its modified timestamp and maintains
normal/archived object passes. Salesforce orders `queryAll` by `SystemModstamp, Id`
and uses the returned `nextRecordsUrl`. The UI shows lifecycle, provider health,
records seen/applied, conflicts and last successful reconciliation. It never claims
real-time sync.

Rate limiting records a safe degraded/rate-limited state and honours a bounded
`Retry-After` where supplied. Authentication/identity failure pauses the job as
`needs_reauth`, disables writeback and does not loop. Definitive non-retryable failures
move the connector to needs attention. Native records and local intelligence remain
available during a provider outage.

## Matching and relationships

Matching order is existing mapping, then one strong unique local identity:

- Account: one exact normalised business domain;
- Contact: one exact non-generic business email; and
- Opportunity: existing provider mapping only—name is never an automatic merge key.

Phone is never a sole merge key. Generic addresses such as `sales@` or `info@` do not
identify a person. Ambiguous/no match creates a new canonical record only when all
required relationships, owner and stage mappings are coherent; otherwise it creates
an import conflict. Provider Account relationships are resolved through an existing
Account mapping. HubSpot's single primary Company projection is used for the
Oryntela-compatible relationship; additional HubSpot Company associations are not
collapsed or guessed. Salesforce AccountId relationships are retained explicitly.

Owner mapping never crosses the active Oryntela organisation membership. An unknown
or inactive owner is held as a provider reference and needs administrator review.
Opportunity stages require an exact provider pipeline/stage mapping. Display-name
similarity is never used. Closed won/lost is the administrator's explicit canonical
mapping, which then feeds the existing Pipeline, Forecast, Targets and Analytics
surfaces.

Salesforce Person Accounts are unsupported in V1. The adapter checks Account schema
support, requests `IsPersonAccount` only where exposed and fails that record/page
closed with `provider_person_account_unsupported`; it never creates an arbitrary
business Account plus Contact pair. Salesforce record-type administration and custom
objects are deferred. Multi-currency Opportunity values retain their three-letter
currency and exact Decimal amount; Oryntela never performs silent FX conversion.

## Provider adapters

### HubSpot

WO-025C's OAuth, encrypted credential, account introspection, link/mapping, Action
preview and meeting-log boundaries are reused. WO-042 adds Company/Contact/Deal page
reads, archive passes, modified-time searches, owner/pipeline discovery, safe create
and update, relationship reads and company association on Contact/Deal create. The
server owns the fixed `https://api.hubapi.com` origin and uses date-versioned
`2026-03` object/association routes. Search results do not establish the canonical
Account relationship, so each incremental Contact/Deal page performs one bounded
association batch read. It does not issue one provider request per record; ambiguous
multi-company results without one primary association remain unmapped for review.

### Salesforce

Salesforce uses an External Client App and web-server authorisation-code flow with
PKCE S256. The callback validates the provider HMAC signature, login identity path,
userinfo organisation/user pair and exact stored organisation identity. API calls use
only the OAuth-returned HTTPS origin after requiring a `*.salesforce.com` hostname
with no credentials, port, path, query or fragment. The browser cannot supply a SOQL
fragment or instance URL.

The single supported API version is `v67.0`; version changes require code/config
review, deterministic contract execution and provider smoke proof. Server-owned SOQL
selects only standard Account, Contact, Opportunity, User and OpportunityStage fields.
`queryAll` preserves deleted-record visibility; unknown/custom fields are ignored.
Updates use the observed external version and a conditional request. Composite/bulk
APIs are deferred until measured quota or dataset evidence justifies them.

Salesforce Account schema discovery retains only the API-version marker and the
allow-listed `IsPersonAccount` capability inside the encrypted credential envelope.
That cache survives request/worker boundaries and is refreshed when the pinned API
version changes, so record reads do not issue a Describe request per record. HubSpot
mapping metadata is fetched only on an explicit administrator configuration load and
is filtered to the fixed field registry before it enters an API response; it is not
looked up while processing each record.

## Writeback and unknown outcomes

The canonical [CRM authority matrix](crm-authority-matrix.md) is the source of truth.
Mapping changes increment the version, return lifecycle to mapping required, turn
writeback off and invalidate stale authority assumptions. Administrator approval is
required after initial sync, owner/stage mapping and every later mapping change.

External create/update requires all of:

1. active connection, tenant membership and CRM write entitlement;
2. connector kill switch on and current mappings approved;
3. writeback explicitly enabled with no open conflict;
4. one exact canonical record and governed allow-listed field set;
5. current provider read for an update;
6. persisted ten-minute preview/fingerprint; and
7. explicit confirmation plus a caller idempotency key.

Definitive success is re-read/verified and stored as an immutable receipt. If the
transport fails after submission, the receipt is `unknown`; automated retry is
forbidden. The reconcile endpoint performs a read-only exact mapped-record lookup and
compares every field in the persisted preview. It creates a new immutable reconciled
receipt only on an exact match. An uncertain create without an exact mapping is held
until inbound sync and human linking establish that identity; it is never guessed or
retried. An inbound echo is absorbed through provider version/receipt and does
not trigger another outbound write. External create supports the three canonical
objects, subject to required relationship/owner/stage fields. External update supports
governed non-provider-authoritative fields. External delete is **not supported**.

## Security, privacy and prompt safety

OAuth state is random, hashed, tenant/user/provider/redirect bound, short-lived and
single-use. Salesforce additionally encrypts the PKCE verifier. Access/refresh tokens
and Salesforce instance origin are inside the AES-256-GCM credential envelope with
tenant/connection associated data. Refresh locks the credential row and persists a
rotated refresh token. Disconnect attempts provider revocation, removes local
credential authority, disables sync/writeback and cancels queued execution while
retaining canonical records and historical provenance.

Provider strings are inert customer data. They can be validated, truncated and
displayed through React escaping but cannot become prompts, system instructions,
provider queries, SQL identifiers, audit content or log messages. No CRM record is
sent to an AI provider by this connector. Oryntela Evidence, intelligence and consent
controls keep their existing provenance and deletion policy.

Ordinary CRM sync consumes no Oryntela Credits. Customers supply their own legitimate
CRM licence. WO-042 used deterministic synthetic fixtures, no customer CRM data and
AUD $0 external spend.

## Operator runbook

### Set up or reconnect

1. Confirm the CRM add-on is writable and the administrator is active.
2. Confirm the one-primary-CRM screen names the expected provider and object scope.
3. Complete provider OAuth; never collect a password, OTP, MFA/recovery code or token.
4. Observe initial sync progress and map every active owner plus required stages.
5. Resolve conflicts, approve the current mapping version and leave writeback off
   until the customer explicitly authorises it.
6. For reconnect, confirm the provider tenant identity is unchanged. A different
   provider tenant requires disconnect/switch review.

### Rate limit, outage or reauthorisation

- `rate_limited`: wait for the bounded retry time; do not manually start repeated
  imports.
- `degraded`/`unavailable`: keep canonical work available and retry through the
  durable worker; never reset all cursors as a first response.
- `needs_reauth`: have an administrator reconnect the same provider tenant. Do not
  replay stale writes.

### Unknown write

Do not click/submit again. Inspect the immutable receipt and exact mapped provider
record, then run reconciliation. If the intended value exists, mark reconciled; if it
does not, return it for a fresh preview and human confirmation. Never delete a receipt
or manufacture a success result.

### Disconnect, switch and rollback

Disconnect immediately stops polling and future writeback. It never deletes the
customer's CRM record or canonical Oryntela sales record. Historical mappings remain
inactive provenance. Connecting the other provider starts a fresh mapping/import
review; old mappings are never reused across providers.

For application rollback, turn off the provider feature flag/connector kill switch,
allow in-flight unknown writes to reconcile and roll the application back. Do not
downgrade migration 0058 while connector records or receipts are operational. A full
organisation erasure follows the existing approved maintenance setting and best-
effort provider revocation.

## Production activation boundary

`HUBSPOT_PRODUCTION_ACTIVE=NO` and `SALESFORCE_PRODUCTION_ACTIVE=NO` are controlling
facts. WO-054 must complete owner-controlled provider app registration, exact HTTPS
redirects, scopes/permission-set policy, credentials in approved secret storage,
provider terms/privacy/subprocessor and Australian cross-border review, authorised
synthetic sandbox smoke tests, quota/health alerts, incident ownership, reconciliation
proof and explicit owner approval. No provider account, app, card, DNS change,
commercial commitment or production connection was created in WO-042.
