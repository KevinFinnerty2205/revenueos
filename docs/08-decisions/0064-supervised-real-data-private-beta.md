# ADR 0064 — Supervised real-data private beta

## Context

Synthetic readiness did not prove controlled tenant creation, provider approvals or recoverability for customer data.

## Decision

Real-data operation is invite-only and operator-provisioned. Production JIT tenant/membership creation is disabled; a content-free idempotent command creates the approved organisation and first admin. Real-data mode requires a target approval reference, support address, encrypted backup key and a restricted feature/provider profile. Partner evidence, not the flag alone, authorises data entry.

## Alternatives

Public self-service signup was rejected because billing, legal acceptance and abuse operations do not exist. A cross-tenant internal admin UI was rejected because it would create a broad support backdoor.

## Consequences

Onboarding is slower but auditable and reversible through existing member/org lifecycles. Unsupervised/commercial beta remains unapproved.
