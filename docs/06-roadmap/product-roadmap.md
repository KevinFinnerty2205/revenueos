# Product roadmap

This sequence reduces trust and platform risk before product breadth. Phase completion depends on tested exit criteria, not dates.

For the focused sprint sequence from the current baseline to private beta, see [Product roadmap to beta](product-roadmap-to-beta.md). For release gates and the exact first-five-company loop, see [MVP and beta scope](mvp-and-beta-scope.md).

## Phase 1 — Foundation

Working web/API shells, auth-ready route protection, organisations/users/memberships, documentation, tests, CI and production build commands. Exit when the Sprint 1 acceptance criteria pass and no later feature is represented as live.

**Status:** Complete.

## Phase 2 — Sales Brain MVP

Verified Clerk identity, tenant-safe company/contact/opportunity records, deliberate meeting intake, private storage, durable transcription/analysis, reviewable insights, tasks and follow-up drafts. Exit requires two-organisation isolation, failure/retry tests, accessibility and deletion controls.

**Status:** In progress. Sprint 2 completed tenant-safe company, contact, opportunity and task records. Sprint 3 completed tenant-safe meetings, participants, deliberately supplied plain-text transcripts and meeting audit history. Verified Clerk identity, media ingestion/storage, transcription, analysis and follow-up drafting remain outstanding.

## Phase 3 — Relationship Memory

Versioned, correctable, source-linked memory plus tenant- and subject-scoped retrieval and cited Q&A. Exit requires deterministic correction/deletion behaviour and adversarial retrieval isolation tests.

## Phase 4 — CRM Integrations

Connector framework followed by one prioritised real sandbox adapter. Reads precede writes; every write needs an explicit diff, approval, idempotency receipt, reconciliation and audit.

## Phase 5 — Recruitment Brain

Recruitment-specific workflows, schemas, evaluations and approved integrations on the shared platform. Sales terminology must not leak into shared domain rules.

## Phase 6 — Customer Success Brain

Customer-success lifecycle, evidence-backed risks and success actions using the same tenant, interaction, memory, job and connector foundations.

## Phase 7 — Enterprise

Only against explicit requirements: SSO/provisioning, custom roles, residency, advanced audit/export, key controls, availability/recovery targets and enterprise integration governance.

## Cross-phase gates

Every phase preserves strict tenant isolation, explicit capture consent, human approval for consequential actions, honest integration status, accessible UI, deterministic mocks, source provenance, deletion behaviour and passing validation.
