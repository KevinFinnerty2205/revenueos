# ADR 0025: keep private beta controls in the modular monolith

## Status

Accepted — WO-009, 25 July 2026.

## Context

RevenueOS needs identity verification, consent, retention, export/deletion,
usage limits, safe health/operations, onboarding and feedback for a small
trusted private beta. Adding a scheduler, queue, second identity provider,
feature-flag platform or administration service would increase the trust and
operational surface beyond the beta need.

## Decision

- Keep Clerk as the only production identity provider and map its verified
  active user/organisation deterministically into the existing identity model.
- Use only `admin` and `member`, with active/disabled state in PostgreSQL.
- Store focused tenant-owned beta tables for notice acknowledgements,
  organisation retention, onboarding, usage, feedback, data requests and safe
  events. Apply composite keys and forced RLS.
- Use environment-deployed server flags and PostgreSQL atomic daily counters.
- Keep retention, export, expired-export purge and organisation deletion as
  explicit tenant-scoped maintenance commands. No scheduler or new worker type
  is added.
- Permit deletion of immutable Revenue Brain rows only inside an explicit
  approved maintenance context that also matches the trusted tenant.
- Keep export as a versioned restricted JSON file with field allowlists and a
  short expiry.
- Preserve the existing AI paths unchanged. Demo data uses the existing mock
  generation path and makes no provider call during seeding.

## Alternatives considered

- Third-party flag/quota/observability platforms: rejected for beta scope and
  unnecessary new data processors.
- Redis/Celery or a maintenance microservice: rejected because bounded commands
  and the existing durable worker/database are sufficient.
- Client-only consent/flags: rejected because security policy must be enforced
  by the API.
- One generic JSON settings/events table: rejected because constraints,
  ownership and retention semantics would be weaker.
- Automatic organisation/identity deletion in Clerk: deferred because connector
  limitations and destructive identity changes require explicit operator review.

## Consequences

The private beta has a small, testable operational surface and no new runtime
service. Operators must schedule commands, perform Clerk lifecycle steps,
manage exports and execute runbooks. Configuration changes require a deployment
or controlled restart. The controls are appropriate for a trusted beta but do
not represent general-availability scale or compliance certification.
