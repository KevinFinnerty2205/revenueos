# ADR 0080 — Canonical membership denial with Clerk session revocation

- **Status:** Accepted
- **Date:** 13 September 2026
- **Work order:** WO-054 immediate user deauthorisation remediation

## Context

A valid Clerk session proves authentication but does not prove that the user still
has current Oryntela authority. Clerk locking also prevents future sign-in without
terminating sessions that are already active. The existing administrator action is
an organisation-membership disable, not a global identity disable, so it must deny
one tenant immediately without converting that action into a global Clerk lock.

## Decision

The canonical `organisation_memberships.status` row remains the server-side access
authority and is checked on every protected API request. Disabling a membership
commits the tenant-scoped disabled state, advances an authority version and records
an authentication watermark before calling Clerk. Work already queued by that user
retains its execution-time active-user and active-membership checks.

After canonical denial commits, the API lists active Clerk sessions for the exact
target Clerk user and selects only sessions whose Clerk
`last_active_organization_id` matches the disabled organisation. It revokes only
those returned session identifiers. The adapter validates the requested user and
organisation, every returned user/session identity and state, response size and
bounded retry count. Provider failures and response-loss ambiguity are recorded with
bounded failure codes; no token, session secret, credential or provider payload is
logged. A Clerk failure cannot roll back canonical denial.

Re-enablement starts while the membership remains disabled, repeats exact-user
session revocation and proceeds only after revocation is confirmed. It restores only
that organisation membership and never recreates a session. It advances the
authentication watermark again at restoration, so JWTs issued before disablement or
while the membership was disabled remain unusable; the user must authenticate
normally again.

This action does not globally lock the Clerk identity. Another organisation's
membership authority is unchanged, and sessions active in another organisation are
not selected for revocation. A session that later changes its active organisation is
still subject to Oryntela's current membership check on every protected request.

## Alternatives considered

- Browser logout only: rejected because it is client-controlled and does not
  terminate other active sessions.
- Clerk lock only: rejected because existing sessions remain active and a
  membership-only action must not globally lock a legitimate multi-organisation
  identity.
- Revoke first, then disable: rejected because provider delay or failure would keep
  application access authorised.
- Re-enable without an authentication watermark: rejected because an old,
  cryptographically valid JWT could regain access after restoration.
- Build an organisation-wide session cache or identity service: rejected as larger
  than the required remediation and an unnecessary stale-authority risk.

## Consequences

Migration `0064_deauthorisation` adds the authority version and authentication
watermark. The production API needs the existing Clerk live secret through the
platform secret manager and the official Clerk Backend API origin. Disable remains
successful when Clerk is unavailable because canonical denial is authoritative;
the response and audit outcome require operator reconciliation. Re-enable fails
closed while revocation is unconfirmed. A future global-user-disable workflow must
be separately designed and may add a Clerk lock without weakening this
organisation-scoped action.
