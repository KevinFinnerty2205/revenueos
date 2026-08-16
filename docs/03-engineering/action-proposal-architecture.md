# Action proposal architecture

## Boundary

The Action Layer remains inside the FastAPI modular monolith. Routes delegate to
`ActionService`; tenant-scoped repositories own persistence. WO-021 generation and
review make no provider call. WO-022 adds a separate execution service and reuses
the existing worker for deterministic connector simulations; there is still no
message broker or live external connector.

`action_proposals` owns identity and lifecycle. `action_proposal_versions` stores
immutable typed content revisions. `action_audit_events` stores metadata-only review
events. All rows carry `organisation_id`; composite foreign keys prevent cross-tenant
attachment and PostgreSQL forced RLS is defence in depth.

## Deterministic generation

The service selects current final sources, validates each source against its owning
aggregate, constructs bounded candidates and hashes canonical source/payload data.
The source fingerprint provides retry idempotency. A semantic key supersedes an older
active proposal when the supported recommendation changes. Generation is limited to
eight proposals per request, 50 active proposals per opportunity and a configurable
organisation daily limit.

No raw transcript or provisional table is queried. Existing Follow-up Email and Next
Best Action artefacts are inputs; the Action Layer does not regenerate them or call an
AI provider.

## Contracts and APIs

FastAPI/Pydantic remains canonical. The discriminated `proposedPayload.kind` union
rejects unknown fields and constrains values, text length, identifiers and recipient
pairs. Routes cover opportunity generation/listing plus Action read, edit, approve,
reject and manual completion. Every proposal response reports
`executionState: not_executed` and `sendReady: false`; execution history is an
independent WO-022 contract.

Migration `0031_action_layer` is reversible. WO-022 migration
`0032_integration_execution` references exact Action versions and is also
reversible. Its downgrade deletes simulation metadata but cannot undo an external
action because no live executor exists.
