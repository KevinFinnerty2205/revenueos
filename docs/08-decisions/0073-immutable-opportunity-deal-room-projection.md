# ADR 0073: immutable allow-listed Opportunity Deal Room projection

- **Status:** Accepted
- **Date:** 2026-09-07

## Context

An Opportunity owner needs a polished way to share selected agreed context and
approved Create outputs with a buyer who does not have an Oryntela account. The normal
Opportunity Workspace contains internal methodology, forecasts, private Evidence,
risks and coaching that must never cross that boundary. Publishing the live
Opportunity object, adding broad public RLS, or serving a mutable “latest” asset would
create unacceptable leakage and drift risk.

WO-043 must cost AUD $0, use current storage only, preserve one room per Opportunity,
support immediate pause/revoke/rotation and avoid buyer identity, editing, tracking,
generic files and WO-044 handover.

## Decision

Store one tenant-scoped structured draft per Opportunity. An explicit reviewed
publication creates a complete immutable numbered snapshot from a positive public
allow-list and atomically points the room to it. Later draft edits have no external
effect until another explicit publication. Approved Business Case and Create
presentation sources are pinned by exact revision.

Issue a high-entropy opaque token, persist only its SHA-256 digest, and display the
plaintext once. Put it in a URL fragment so it does not enter HTTP URLs or referrers;
exchange it in a no-store POST. Optional expiry and transactional rotation/revocation
are first-class.

Keep forced tenant RLS on every table. Public access uses narrow PostgreSQL
`SECURITY DEFINER` functions that can return only the current snapshot or one pinned
presentation's storage metadata after all token, room and Opportunity lifecycle
checks. Do not grant anonymous ordinary tenant-table access. The service validates the
stored public schema again before responding.

Assign entitlement to the existing Create module, including the existing Complete
trial behaviour. Charge no Credits. Reuse current private Create storage and support
only approved presentation downloads plus credential-free HTTPS links.

## Alternatives rejected

- **Serialise the Opportunity and omit blocked fields:** a negative list will drift as
  internal fields grow and is too easy to leak.
- **Public RLS policy on tenant tables:** weakens the normal tenant boundary and grants
  more query authority than a link requires.
- **Mutable live room or “latest asset”:** silently changes buyer-visible terms and
  destroys publication evidence.
- **Plaintext token persistence or query-string links:** increases disclosure through
  databases, exports, logs, browser history and referrers.
- **Buyer accounts/OTP:** adds an identity and delivery system without a V1 need.
- **Generic uploaded files or external portal provider:** expands into a Files product,
  introduces storage/commercial obligations and breaches the AUD $0 boundary.
- **Buyer comments, tracking or automatic email:** materially expands privacy,
  authority and messaging scope.

## Consequences

Sellers must republish deliberate changes and must copy a new/rotated link when it is
shown. A lost plaintext link cannot be recovered; rotation safely creates another.
Public presentation downloads depend on the approved stored asset remaining available
under existing retention rules. Closed or archived Opportunities deny public access,
and PostgreSQL pauses published rooms on that transition.

The V1 buyer cannot edit or comment, and Oryntela records no views. Branding is limited
to current organisation/customer names and neutral visual hooks. A future Files
product, richer branding, reviewed Engage sharing or Closed-Won handover can integrate
later without changing this publication boundary.
