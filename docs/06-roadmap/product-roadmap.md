# Product roadmap

This sequence reduces trust and platform risk before product breadth. Phase completion depends on tested exit criteria, not dates.

For the approved post-WO-009 direction, see the
[Interaction Intelligence roadmap](interaction-intelligence-roadmap.md). The older
[product roadmap to beta](product-roadmap-to-beta.md) retains integration-led
planning and completed-baseline context. Release gates and the existing
first-five-company loop remain in [MVP and beta scope](mvp-and-beta-scope.md).

## Phase 1 — Foundation

Working web/API shells, auth-ready route protection, organisations/users/memberships, documentation, tests, CI and production build commands. Exit when the Sprint 1 acceptance criteria pass and no later feature is represented as live.

**Status:** Complete.

## Phase 2 — Sales Brain MVP

Verified Clerk identity, tenant-safe company/contact/opportunity records, deliberate meeting intake, private storage, durable transcription/analysis, reviewable insights, tasks and follow-up drafts. Exit requires two-organisation isolation, failure/retry tests, accessibility and deletion controls.

**Status:** Current implementation through WO-009. Sprints 2–3 provide tenant-safe
business entities, meetings, participants, deliberately supplied plain-text
transcripts and audit history. WO-004A1–C6 and WO-005/006A–D provide the durable AI
foundation, optional server-side OpenAI execution and ten-capability unified Meeting
Intelligence. WO-007/008A/B provide Opportunity Workspace plus immutable Revenue
Brain snapshots and deterministic longitudinal reasoning. WO-009 adds verified
Clerk organisation sessions and controlled private-beta consent, retention,
export/deletion, usage, onboarding, feedback, administration and operational
foundations. Target-environment customer-content approval, media
ingestion/storage, transcription and approved sending/integrations remain
outstanding.

## Phase 3 — Interaction Intelligence Platform

Evolve Meeting Intelligence through an additive Interaction parent and
source-neutral Evidence model. Deliver preparation, immediate AI Debrief/Voice
Journal and visual evidence before recording/native mobile, selected online capture,
documents/emails and narrowly justified live intelligence. Exit requires usable
face-to-face intelligence without transcript upload, visible provenance/conflict,
Meeting/Revenue Brain compatibility, deletion and beta operational gates. See the
[Interaction Intelligence roadmap](interaction-intelligence-roadmap.md).

**Status:** Blueprint complete in WO-010; implementation not started or authorised.

## Phase 4 — Relationship Memory

Versioned, correctable, source-linked memory plus tenant- and subject-scoped retrieval and cited Q&A. Exit requires deterministic correction/deletion behaviour and adversarial retrieval isolation tests.

## Phase 5 — CRM Integrations

Connector framework followed by one prioritised real sandbox adapter. Reads precede writes; every write needs an explicit diff, approval, idempotency receipt, reconciliation and audit.

## Phase 6 — Recruitment Brain

Recruitment-specific workflows, schemas, evaluations and approved integrations on the shared platform. Sales terminology must not leak into shared domain rules.

## Phase 7 — Customer Success Brain

Customer-success lifecycle, evidence-backed risks and success actions using the same tenant, interaction, memory, job and connector foundations.

## Phase 8 — Enterprise

Only against explicit requirements: SSO/provisioning, custom roles, residency, advanced audit/export, key controls, availability/recovery targets and enterprise integration governance.

## Cross-phase gates

Every phase preserves strict tenant isolation, explicit capture consent, human approval for consequential actions, honest integration status, accessible UI, deterministic mocks, source provenance, deletion behaviour and passing validation.
