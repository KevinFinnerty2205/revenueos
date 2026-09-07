# WO-043 — Simple Opportunity Deal Room

- **Branch:** `codex/wo-043-simple-opportunity-deal-room`
- **Baseline:** `e5936c046423ab0a059b5d2c12a4812b4ab8db55`
- **Status:** implemented; awaiting engineering review
- **Migration:** `0059_opportunity_deal_room`
- **Data/spend:** deterministic synthetic fixtures only; no customer data, external
  provider, new storage or spend (AUD $0)

## Outcome

WO-043 adds one read-only buyer Deal Room beneath an active Opportunity. The
Opportunity owner or organisation administrator creates and edits a private bounded
draft, reviews it, and explicitly publishes an immutable customer-facing revision.
The seller can pause access, republish, revoke the room, rotate its link and set an
optional expiry. A changed draft never silently changes an already published room.

The buyer opens a polished standalone page without an Oryntela account. It can show an
overview, an approved Business Case projection, approved commercial copy, selected
stakeholder names/roles/companies, shared milestones/next steps, exact approved Create
presentation downloads, safe HTTPS resources and a next meeting/decision time. The
full application navigation and internal Opportunity Workspace do not appear.

## Security and authority

- A positive allow-list builds the public projection; the service never serialises an
  Opportunity or internal intelligence object.
- Unknown fields are rejected. Internal forecasts, MEDDIC, coaching, risks, notes,
  Evidence, competitor strategy, provider cost and Credit economics have no path into
  the public schema.
- Business Case formulas/inputs and internal source IDs are absent from the external
  response. Only customer-facing approved outputs are copied.
- Presentation resources require the same tenant and Opportunity and an exact approved,
  ready, available revision. Downloads re-authorise and checksum the asset without
  exposing its storage path.
- Share tokens contain 32 random bytes; only a unique SHA-256 digest is stored. Links
  use a browser fragment and tokens appear only in no-store POST bodies. Rotation
  invalidates the old link transactionally.
- All four tables have forced PostgreSQL RLS. Public reads use two bounded database
  functions rather than anonymous tenant-table authority.
- Invalid, expired, paused, revoked, closed and missing links use a safe non-enumerating
  response. Public lookup is rate-limited without persistent IP or fingerprint data.
- API and web controls include no-store, no-referrer, noindex/nofollow/noarchive, CSP,
  clickjacking denial, content-type protection and production HSTS.

## Product and commercial boundary

The Deal Room belongs to the existing Create entitlement. Complete and Enterprise
plans include it, and the existing Complete trial therefore does too; current add-on
rules also apply. No new package or price is introduced and Deal Room actions consume
no Credits.

There is no general file upload. V1 reuses current approved Create presentations and
supports bounded external HTTPS links. Buyer accounts, editing, comments,
acknowledgement, e-signature, payments, tracking, AI drafting and automatic email/
Engage sharing are deferred. Seller copy-link is the complete V1 sharing flow.

Closed Won and Closed Lost both make the room unavailable and pause a currently
published room. This is not a Closed-Won handover; WO-044 is not implemented.

## Data lifecycle

Organisation export version 36 includes Deal Room configuration, immutable snapshots,
source fingerprints, link lifecycle metadata and audit events, but no plaintext or
hashed token. Approved organisation deletion removes links/revisions/rooms and makes
all prior links unusable. Existing retention and Opportunity soft-archive policies
remain authoritative; no legal retention period was invented.

## Verification and handoff

Backend, shared-contract, component and Playwright coverage exercises the full
lifecycle, security boundary, pinned revisions, malicious text, unavailable resources,
mobile layout and accessible interaction. The complete repository gate, desktop/390px
visual evidence and GitHub CI status are recorded in the draft PR and final handoff.

Visual QA evidence:

- [Seller editor — desktop](assets/wo-043/opportunity-deal-room-editor-desktop.png)
- [Published buyer room — desktop](assets/wo-043/public-deal-room-desktop.png)
- [Published buyer room — 390 px](assets/wo-043/public-deal-room-mobile.png)
- [Buyer resources and next steps — 390 px](assets/wo-043/public-deal-room-mobile-resources.png)
- [Unavailable/revoked link — 390 px](assets/wo-043/public-deal-room-unavailable-mobile.png)

See [Opportunity Deal Room architecture](../03-engineering/opportunity-deal-room.md)
and [ADR 0073](../08-decisions/0073-immutable-opportunity-deal-room-projection.md).
