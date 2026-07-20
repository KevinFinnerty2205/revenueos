# RevenueOS documentation

This is the canonical product and engineering documentation index. Documents distinguish **current implementation** from **pilot**, **beta**, **later** and **future** direction. A target document does not authorise implementation.

## Start here

1. [Company vision](00-company/vision.md)
2. [Master product blueprint](01-product/master-product-blueprint.md) — primary product contract through beta
3. [MVP and beta scope](06-roadmap/mvp-and-beta-scope.md) — release gates and the exact first-five-company loop
4. [Product roadmap to beta](06-roadmap/product-roadmap-to-beta.md) — proposed sprint sequence
5. [Current application architecture](03-engineering/architecture.md) — what exists now
6. [ADR 0003: product blueprint and beta sequencing](08-decisions/0003-product-blueprint-and-beta-sequencing.md)

## 00 — Company

- [Vision](00-company/vision.md)

## 01 — Product

- [Master product blueprint](01-product/master-product-blueprint.md)
- [Personas and jobs](01-product/personas-and-jobs.md)
- [User journeys](01-product/user-journeys.md)
- [Product overview](01-product/product-overview.md)

## 02 — Design

- [Information architecture](02-design/information-architecture.md)
- [Core workflows](02-design/core-workflows.md)
- [Design principles](02-design/design-principles.md)

## 03 — Engineering

### Current implementation

- [Application architecture](03-engineering/architecture.md)
- [AI database foundation](03-engineering/ai-database-foundation.md)
- [AI domain services](03-engineering/ai-domain-services.md)
- [AI worker and durable job queue](03-engineering/ai-worker-queue.md)
- [AI provider abstraction](03-engineering/ai-provider-abstraction.md)
- [OpenAI provider integration](03-engineering/openai-provider-integration.md)
- [Prompt registry and structured output](03-engineering/prompt-registry-and-structured-output.md)
- [Executive Summary intelligence](03-engineering/executive-summary-intelligence.md)
- [Meeting Decisions intelligence](03-engineering/meeting-decisions-intelligence.md)
- [Meeting Action Items intelligence](03-engineering/meeting-action-items-intelligence.md)
- [Meeting Risks & Blockers intelligence](03-engineering/meeting-risks-blockers-intelligence.md)
- [Meeting Open Questions intelligence](03-engineering/meeting-open-questions-intelligence.md)
- [Follow-up Email Composer](03-engineering/follow-up-email-composer.md)
- [Unified Meeting Intelligence workspace](03-engineering/unified-meeting-intelligence.md)
- [API reference](03-engineering/api.md)
- [Security and privacy baseline](03-engineering/security-and-privacy.md)
- [Development guide](03-engineering/development-guide.md)
- [Deployment guide](03-engineering/deployment-guide.md)

### Target through beta

- [Target domain model](03-engineering/target-domain-model.md)
- [Privacy, security and trust model](03-engineering/privacy-security-and-trust-model.md)

## 04 — AI

- [AI documentation index](04-ai/README.md)
- [AI system blueprint](04-ai/ai-system-blueprint.md)

## 05 — Integrations

- [Integrations documentation index](05-integrations/README.md)
- [Integration strategy](05-integrations/integration-strategy.md)

## 06 — Roadmap

- [Product roadmap to beta](06-roadmap/product-roadmap-to-beta.md)
- [MVP and beta scope](06-roadmap/mvp-and-beta-scope.md)
- [Long-range product roadmap](06-roadmap/product-roadmap.md)

## 07 — Sprint records

- [Sprint 1: foundation](07-sprints/sprint-01-foundation.md)
- [Sprint 2: core business entities](07-sprints/sprint-02-core-business-entities.md)
- [Sprint 3: Meeting Domain Foundation](07-sprints/sprint-03-meeting-domain.md)
- [WO-004A1: AI Database Foundation](07-sprints/wo-004a1-ai-database-foundation.md)
- [WO-004A2: AI Repository, Service, Lifecycle and Audit Foundation](07-sprints/wo-004a2-ai-domain-services.md)
- [WO-004B1: AI Worker and Durable Job Queue](07-sprints/wo-004b1-ai-worker-queue.md)
- [WO-004B2: AI Provider Abstraction and Deterministic Mock Provider](07-sprints/wo-004b2-ai-provider-abstraction.md)
- [WO-004B3: Prompt Registry and Structured Output Validation](07-sprints/wo-004b3-prompt-registry.md)
- [WO-004C1: Executive Summary Intelligence Capability](07-sprints/wo-004c1-executive-summary.md)
- [WO-004C1A: Production OpenAI Provider Integration](07-sprints/wo-004c1a-openai-provider.md)
- [WO-004C2: Meeting Decisions Intelligence](07-sprints/wo-004c2-meeting-decisions.md)
- [WO-004C3: Meeting Action Items Intelligence](07-sprints/wo-004c3-meeting-action-items.md)
- [WO-004C4: Meeting Risks & Blockers Intelligence](07-sprints/wo-004c4-meeting-risks-blockers.md)
- [WO-004C5: Meeting Open Questions Intelligence](07-sprints/wo-004c5-meeting-open-questions.md)
- [WO-004C6: Follow-up Email Composer](07-sprints/wo-004c6-follow-up-email-composer.md)
- [WO-005: Unified Meeting Intelligence workspace](07-sprints/wo-005-unified-meeting-intelligence.md)

## 08 — Decision records

- [ADR 0001: foundation architecture](08-decisions/0001-foundation-architecture.md)
- [ADR 0002: tenant-owned business entities](08-decisions/0002-tenant-business-entities.md)
- [ADR 0003: product blueprint and beta sequencing](08-decisions/0003-product-blueprint-and-beta-sequencing.md)
- [ADR 0004: tenant-owned Meeting Domain](08-decisions/0004-meeting-domain.md)
- [ADR 0005: tenant-owned AI database foundation](08-decisions/0005-ai-database-foundation.md)
- [ADR 0006: AI domain service boundaries](08-decisions/0006-ai-domain-service-boundaries.md)
- [ADR 0007: PostgreSQL-backed AI worker queue](08-decisions/0007-postgresql-ai-worker-queue.md)
- [ADR 0008: provider-neutral AI execution](08-decisions/0008-provider-neutral-ai-execution.md)
- [ADR 0009: versioned prompts and strict structured output](08-decisions/0009-versioned-prompts-and-strict-output.md)
- [ADR 0010: current-transcript Executive Summary execution](08-decisions/0010-current-transcript-executive-summary.md)
- [ADR 0011: server-side OpenAI Responses provider](08-decisions/0011-server-side-openai-responses-provider.md)
- [ADR 0012: current-transcript Decisions execution](08-decisions/0012-current-transcript-decisions.md)
- [ADR 0013: current-transcript Action Items execution](08-decisions/0013-current-transcript-action-items.md)
- [ADR 0014: current-transcript Risks & Blockers execution](08-decisions/0014-current-transcript-risks-blockers.md)
- [ADR 0015: current-transcript Open Questions execution](08-decisions/0015-current-transcript-open-questions.md)
- [ADR 0016: compose customer content from validated intelligence only](08-decisions/0016-validated-intelligence-composers.md)
- [ADR 0017: derive a unified Meeting Intelligence workspace](08-decisions/0017-derived-meeting-intelligence-workspace.md)

## Current delivery boundary

Sprints 1–3 and WO-004A1/A2/B1/B2/B3/C1/C1A/C2/C3/C4/C5/C6/005 are complete.
An authenticated user can generate and read Executive Summary, Key Decisions,
Action Items, Risks & Blockers, Open Questions and Follow-up Email through one
derived Meeting Intelligence workspace while each capability remains independently
persisted and traceable. One aggregate read and polling flow exposes safe overall
state and progress; one idempotent action creates only missing work and queues the
composer after its four validated customer-safe artefacts are ready. Mock remains
the deterministic no-network default; optional server-side OpenAI supports all six
capabilities. Transcript-grounded extractors send the selected transcript to
OpenAI only when configured; Follow-up Email sends only its validated artefact
projection and never queries or transmits transcript text. There is no send,
editing, approval, question answering, provider UI, recording, media storage,
transcription, external integration, production Clerk verification, billing or
mobile application. Assistant remains a placeholder.

Do not use production customer data. Production identity, consent evidence, retention/export/erasure and operational controls are incomplete. Future sprints remain unauthorised until a separate work order is approved.
