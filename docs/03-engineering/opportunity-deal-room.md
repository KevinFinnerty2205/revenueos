# Opportunity Deal Room architecture

## Purpose and boundary

WO-043 adds one small customer collaboration space to one active, tenant-owned
Opportunity. It is not a file store, generic portal, CRM replacement, signature
system, handover workflow or customer account system. The buyer experience is
read-only and does not use the authenticated application shell.

Deal Room administration belongs to the existing `create` module entitlement.
Complete and Enterprise include Create; a current trial receives the Complete module
set; an authorised add-on can also grant Create. Deal Room operations consume no
Oryntela Credits and use no external provider or new storage service.

## Data and lifecycle

Migration `0059_opportunity_deal_room` adds four tenant-owned tables:

- `deal_rooms` stores the single bounded draft for an Opportunity and the pointer to
  its current published revision. A tenant/Opportunity unique constraint enforces one
  room.
- `deal_room_revisions` stores immutable, numbered publication snapshots and their
  SHA-256 content fingerprints.
- `deal_room_access_links` stores only a unique SHA-256 digest of each high-entropy
  token plus creation, optional expiry and revocation metadata.
- `deal_room_audit_events` stores actor/action metadata, changed section names and
  counts—not customer-facing content or tokens.

The coherent lifecycle is `draft → published ↔ paused`, with `revoked` as an explicit
link-invalidating state. Republishing creates another immutable snapshot and atomically
changes the current pointer. Editing the draft never changes what a buyer sees. A
revoked room may be deliberately published again, which issues a new link.

Closing Won, closing Lost or archiving the Opportunity makes public resolution fail.
PostgreSQL also pauses a currently published room in the same database transaction.
There is no indefinite Closed-Won handover: WO-044 remains separate and unimplemented.

## Publication allow-list

The service builds the public snapshot field-by-field. It never serialises an
Opportunity, Contact, Evidence or Sales Brain object. The external response can contain
only:

- seller organisation name, customer company name and Opportunity display name;
- seller-authored plain-text overview and explicitly reviewed commercial summary;
- one explicitly selected approved Business Case revision, reduced to approved
  customer-facing output labels and display values;
- bounded stakeholder name, role, company and seller/customer party;
- bounded milestone title, owner party, target date, simple status and public note;
- bounded credential-free HTTPS resources and explicitly selected, approved, ready
  Create presentation revisions; and
- an explicitly supplied next meeting or decision timestamp.

The schema rejects unknown fields. It therefore cannot accept forecast probability,
MEDDIC/MEDDPICC, coaching, internal notes, risks, private Evidence, provider costs,
Credit economics or other internal sales state. Text is bounded plain text. React
renders it as text; arbitrary HTML and scripts are never interpreted. No AI or prompt
path is involved, so untrusted CRM text cannot instruct the feature to retrieve or
publish internal data.

Business Case formulas, raw inputs and non-customer-facing outputs are excluded. The
external response also omits internal case, version and presentation identifiers.
Those exact source references stay inside the immutable server snapshot so publication
and authorised export retain provenance and a presentation download can be checked
against its pinned source. The public database function independently rebuilds every
root and nested object from the same positive allow-list; it does not return the raw
server snapshot or rely on the web client to hide fields.

## Link and public database boundary

Publication and rotation generate 32 random bytes with `secrets.token_urlsafe(32)`.
Only `SHA-256(token)` is persisted; the plaintext is returned once and cannot be
recovered. The browser link uses `/deal-room#access=<token>`. URL fragments are not
sent in the HTTP request or Referer. The buyer page exchanges the token in a no-store
POST body. Request logging records method/path/status and never bodies.
After capturing a valid-shaped fragment into page memory, the buyer page replaces the
current history entry with `/deal-room`. Section navigation cannot clear or replace
the captured authority, and neither the Clerk browser provider nor Clerk middleware
runs for this public route.

Internal routes derive the organisation from verified auth, require Create access and
permit the Opportunity owner or an organisation administrator. Every repository query
has explicit organisation and Opportunity predicates.

All four tables use forced PostgreSQL RLS. The unauthenticated path does not receive a
tenant setting or ordinary table authority. Two `SECURITY DEFINER` functions expose
only (a) the current validated snapshot and (b) storage metadata for one presentation
resource already present in that snapshot. They require an active digest, unexpired
link, published room and open/unarchived Opportunity. Expiry is evaluated against the
database clock rather than caller-supplied time. PostgreSQL uses the hash index; the
high-entropy token is never compared or stored in plaintext.

Both functions use fixed SQL, fully qualified objects and
`search_path = pg_catalog, public`. Execute is deliberately granted through PostgreSQL
`PUBLIC` because the separately provisioned application-role name is deployment
specific; this grants no table or schema-create authority, and the 256-bit bearer
digest plus the function's exact projection remains the complete authority boundary.
Trigger helpers revoke `PUBLIC` execution. A database trigger also rejects a
published-revision pointer unless that immutable revision belongs to the same tenant
and room, and both public functions repeat the room/revision join predicate.

The resource endpoint rechecks the pinned presentation as approved, ready, available
and not archived, then verifies byte count and SHA-256 checksum before returning the
existing PPTX. It never exposes a storage key. External URLs are not fetched by the
server and must be HTTPS with a hostname and without embedded credentials.

Rotation revokes the old link before inserting the replacement in the same
transaction. Optimistic draft/room versions and consistently ordered Opportunity/room
row locks reject competing publishes. Revocation is intentionally safety-biased: once
its row lock is acquired, an authorised confirmed revoke terminates the then-current
link even if a competing publish advanced the submitted lock version. A publish that
runs after revocation fails stale. Public reads resolve one current revision, so a
page never combines sections from different publications.

## Browser privacy and abuse controls

The API and web route use `Cache-Control: no-store`, `Referrer-Policy: no-referrer`,
`X-Frame-Options: DENY`, `frame-ancestors 'none'`, content-type protections and a
restrictive Permissions Policy. Production adds HSTS through the existing API
middleware. The web route emits `X-Robots-Tag: noindex, nofollow, noarchive` and matching
metadata; these are indexing controls, not access control.

Public token lookup and resource download share a bounded per-process sliding-minute
rate limiter scoped to the client-address/bearer pair, so abuse against one room does
not globally lock unrelated rooms behind the same proxy address. It retains only an
ephemeral keyed digest of that pair and no plaintext IP or token, fingerprint,
geolocation, third-party signal, view count or last-viewed record.
Invalid, expired, paused, revoked, closed and unavailable-resource paths return the
same safe customer message where applicable.

## Bounded content

- overview: 2,000 characters;
- commercial summary: 1,500 characters;
- stakeholders: 12, with 120-character names/roles and 200-character companies;
- milestones: 20, with 160-character titles and 500-character notes;
- resources: 10, with 160-character titles and 2,048-character HTTPS URLs; and
- stable random IDs within each stakeholder, milestone and resource list.

V1 reuses existing approved Business Case and Create presentation data. General file
upload is deferred because WO-043 must not become a Files product or add storage.
Customer editing, comments, acknowledgements, e-signature, payments, buyer accounts,
email auto-send, Engage drafts, AI drafting and buyer view analytics are also deferred.
The seller copies the one-time link and chooses how to share it.

## Export, deletion and retention

Organisation export version 36 contains Deal Room draft configuration, immutable
published snapshots and fingerprints, link lifecycle metadata and audit metadata. It
contains neither plaintext tokens nor token hashes. Approved organisation deletion
removes audits, links, revisions and rooms before Opportunity records; links stop
resolving immediately. Normal Opportunity lifecycle remains soft archive, and the
public service denies archived or closed Opportunities. No new statutory retention
period is invented.

## Verification

Deterministic API tests cover lifecycle, one-room uniqueness, stale publication,
allow-list injection, token hashing, audit/export token absence, rotation, expiry,
closed Opportunity access, unrelated-seller denial, approved source validation,
revision pinning and deleted presentation handling. PostgreSQL coverage includes
forced RLS, non-bypass runtime-role responses, function ownership/execute/search-path
metadata, nested projection stripping, pointer integrity, immutable revisions,
concurrent create/publish, publish rollback, publish/revoke and publish/close races.
Component and Playwright tests cover text-safe rendering, fragment scrubbing and
section navigation, unavailable UX, headings, links/download controls, keyboard
focus, 390px overflow and noindex/no-referrer headers.
