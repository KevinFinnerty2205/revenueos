# ADR 0079 — Immutable organisation Terms acceptance

- **Status:** Accepted for engineering; final legal publication and production acceptance blocked
- **Date:** 11 September 2026
- **Work order:** WO-054 productionisation

## Context

The owner approved the substantive Terms drafting positions but did not approve a
final version, effective date or publication. A new organisation must nevertheless
be unable to start its first trial or paid checkout without an authenticated person
with organisation authority explicitly accepting the exact current Terms. Support
must not accept silently for a customer and a browser-only checkbox is not sufficient
authority.

## Decision

Store one tenant-owned, immutable `terms_acceptances` event for each exact Terms
release accepted by an organisation. The server derives the organisation and user
from verified active membership and permits only the existing `admin` role to bind
the organisation. It also derives the acceptance time, Terms status/version/SHA-256
fingerprint/effective date and the linked Privacy Notice identity. The client supplies
only an explicit true authority-and-acceptance assertion and one bounded source.

The Terms fingerprint covers canonical Markdown legal content, not rendered page
navigation or footer content. A changed release identity requires a new event; no
existing event is rewritten. PostgreSQL enables and forces tenant RLS, requires a
tenant-consistent membership foreign key and rejects updates or ordinary deletes at
the database boundary. Approved organisation deletion may delete evidence only after
setting the existing transaction-local maintenance authority. Organisation export
includes the content-minimised acceptance evidence.

Trial start, initial plan assignment and paid Checkout all require a matching current
event server-side before any commercial or provider mutation. Existing active paid
subscriptions can change plan without a new acceptance unless a future approved
Terms release deliberately requires it. A Privacy Notice change does not invalidate
an unchanged Terms acceptance; each event retains the exact notice that was presented
when that Terms release was accepted. Repeated or concurrent acceptance of the same
release serialises on the organisation row and converges on one event.

Checkout operations retain a tenant-consistent foreign key to the exact acceptance
used for their request fingerprint. Checkout rechecks that authority immediately
before provider account or session creation, so a changed required Terms release
fails without a provider side effect and an old idempotency key cannot return a
Checkout created under different Terms.

During development and tests, the release registry identifies the exact owner-review
draft on PR #88 at commit `49761341636f310ade1c42bf25a4699bdbf758c3`.
Staging and production acceptance remain unavailable until both legal documents have
owner-approved statuses and effective dates. Production preflight independently fails
while that release lock is incomplete.

## Alternatives considered

- Rely on a browser checkbox or Checkout redirect: rejected because either can be
  bypassed and neither provides durable server authority.
- Let support record acceptance: rejected because support is not the customer
  organisation's accepting person.
- Update one organisation row when Terms change: rejected because it destroys the
  evidence for the earlier release.
- Add device or browser fingerprinting: rejected as unnecessary personal data.
- Add e-signature or Enterprise order handling: deferred; a later reviewed authority
  model can add a separate evidence source without weakening this event.

## Consequences

Migration `0063_terms_acceptance` owns the new table and security controls. The
acceptance endpoint and UI are deliberately small, but final production readiness
still depends on locking the final Terms and Privacy identities, merging the legal
content change, completing provider/retention decisions and passing the named target
gate. This ADR does not approve publication, production activation, customer data or
spend.
