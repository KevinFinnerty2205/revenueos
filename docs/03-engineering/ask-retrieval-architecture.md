# Ask RevenueOS retrieval architecture

## Boundary

Ask v1 is a bounded read-only composition inside the existing FastAPI modular
monolith. `AskRevenueOSService` classifies a question into a fixed taxonomy,
`AskRepository` performs tenant-scoped structured reads, and strict Pydantic contracts
compose and validate the response. It does not generate SQL, accept a query plan from
the browser, crawl the public web or invoke a provider.

## Request flow

1. Require the server feature flag and current data-notice acknowledgement.
2. Require an active organisation membership from verified authentication context.
3. Resolve the explicit Opportunity, Account or workspace scope with organisation
   predicates; workspace scope is limited to open Opportunities owned by the user.
4. Deterministically classify the question. Instruction-like and public-web requests
   are routed to safe `unknown` answers.
5. Retrieve only bounded source families relevant to that class.
6. Rank structured/current sources, bound unique candidates by source count and
   context characters, and compose one answer.
7. Validate every point/action citation against the retrieved source set.
8. Atomically reserve daily quota and persist a metadata-only audit event.

## Source hierarchy

The implementation reuses, rather than re-derives, current product intelligence:

1. Opportunity metadata and RevenueOS Daily/current Action state where the question
   asks for current work or focus;
2. current Methodology projections and explicit field states;
3. current Revenue Brain longitudinal insights;
4. verified, available, accepted document/email Evidence snapshots with provenance;
5. latest final Revenue Brain artefact bundle for a completed interaction;
6. current reviewable/approved Action versions and existing Next Best Action.

Raw transcripts are not searched by Ask v1. Provisional live signals, rejected
candidate evidence, deleted/unavailable Evidence, superseded artefacts and incomplete
meeting bundles are excluded. Accepted snapshot evidence IDs are validated in one
batched query, avoiding per-item source enumeration.

## Bounds and performance

Defaults are configurable server-side:

| Bound | Default |
| --- | ---: |
| question characters | 1,000 |
| returned/retrieved sources | 12 |
| retrieved context characters | 16,000 |
| workspace Opportunity results | 10 |
| latest account/workspace structured rows | 20 per family |
| provider calls | 0 |

Sorting is deterministic by policy rank, recency and source ID. Account queries are
bounded, workspace queries start from a user-owned Opportunity set, and related rows
are read in set-based repository calls. Search remains its separate three-record-type
deterministic request and never calls Ask.

## Failure behaviour

Missing/inaccessible scope is a safe 404. Missing membership is 403. Disabled feature
is 404. Quota exhaustion is 429 with user-safe codes. Invalid source content is
skipped; an empty candidate set becomes `unknown`. No exception may cause a fallback
to broader scope, public research or unvalidated prose.

The deterministic composer is an intentional v1 decision. A future provider-backed
composer would require an approved provider allowlist, a versioned prompt, strict
output validation, the same citation verifier, privacy/retention review and one-call
bounded execution; it is not authorised by WO-025B.
