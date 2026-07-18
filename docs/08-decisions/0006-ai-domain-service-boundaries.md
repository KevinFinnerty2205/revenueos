# ADR 0006 — AI domain service boundaries

**Status:** Accepted

**Date:** 2026-07-18

## Context

WO-004A1 introduced tenant-owned AI job and append-only artefact persistence without application behaviour. WO-004A2 needs a safe internal layer for idempotent job creation, explicit lifecycle preparation and typed infrastructure-test artefacts, while workers, providers, prompts, APIs and genuine intelligence remain unauthorised.

The existing application already uses tenant-aware repositories, services, `PublicAPIError`, transaction-local forced RLS and meeting audit history.

## Decision

- Add focused `AIJobRepository` and `AIArtifactRepository` modules with an explicit organisation parameter on every operation.
- Keep transaction ownership in the service flow using the repository's session boundary, matching existing application conventions.
- Require a trimmed non-empty service idempotency key and use the database unique constraint as the concurrency arbiter.
- Model lifecycle policy as an explicit allow-list. Increment attempts only when entering `running`; preserve attempts while preparing `failed` back to `pending`.
- Treat `completed` and `cancelled` as terminal.
- Permit `running` to `cancelled` because the existing schema has cancellation timestamps and a cancelled status.
- Validate infrastructure-test content with a strict Pydantic schema and persist only its normalised JSON form.
- Allocate append-only artefact versions optimistically, retrying one uniqueness conflict before returning a safe conflict.
- Extend the existing meeting audit table rather than creating a second audit system. Add a metadata-only JSON field and AI actions/entity types.
- Return tenant-scoped not-found errors for foreign identifiers so services do not disclose another organisation's records.
- Keep all new behaviour internal; add no API, worker, lock, provider, prompt or UI.

## Alternatives considered

- **New AI-specific audit table:** rejected because it would duplicate actor, meeting, tenant and chronology semantics already owned by meeting history.
- **Application-only idempotency:** rejected because it cannot safely arbitrate concurrent requests.
- **Row locks or a job claim method:** rejected because execution/worker semantics are outside WO-004A2.
- **Mutable latest artefact:** rejected because WO-004A1 deliberately established append-only reviewable versions.
- **Unstructured JSON validation:** rejected because future provider output must never bypass a typed contract.
- **Expose internal services through API routes now:** rejected because no product/API contract was authorised.
- **Globally query a foreign ID to return a special cross-tenant error:** rejected because that leaks record existence and weakens tenant query conventions.

## Consequences

Positive:

- application policy now independently validates the tenant trace before database enforcement;
- identical requests are safe under normal and concurrent execution;
- lifecycle rules are reviewable and testable without pretending work executes;
- artefact JSON has a strict versioned contract;
- AI audit events remain content-minimised and atomic with state changes; and
- future worker/provider layers have narrow repository/service seams.

Trade-offs:

- optimistic lifecycle changes do not yet solve concurrent worker claims;
- artefact version allocation may return a safe conflict after bounded contention;
- the meeting audit schema migration widens one column and adds JSON metadata;
- transcript version identity still lacks historical source snapshots; and
- internal services provide no user value until separately authorised API/worker layers arrive.

## Follow-up triggers

Create or update an ADR before introducing job claiming/locks, worker leases, retry scheduling, providers, prompts, additional job/artefact types, AI API/UI access, transcript snapshots or retention/erasure rules.

## Related documents

- [AI domain services](../03-engineering/ai-domain-services.md)
- [AI database foundation](../03-engineering/ai-database-foundation.md)
- [WO-004A2 sprint record](../07-sprints/wo-004a2-ai-domain-services.md)
- [Security and privacy](../03-engineering/security-and-privacy.md)
