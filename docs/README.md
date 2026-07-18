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
- [API reference](03-engineering/api.md)
- [Security and privacy baseline](03-engineering/security-and-privacy.md)
- [Development guide](03-engineering/development-guide.md)

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

## 08 — Decision records

- [ADR 0001: foundation architecture](08-decisions/0001-foundation-architecture.md)
- [ADR 0002: tenant-owned business entities](08-decisions/0002-tenant-business-entities.md)
- [ADR 0003: product blueprint and beta sequencing](08-decisions/0003-product-blueprint-and-beta-sequencing.md)
- [ADR 0004: tenant-owned Meeting Domain](08-decisions/0004-meeting-domain.md)
- [ADR 0005: tenant-owned AI database foundation](08-decisions/0005-ai-database-foundation.md)
- [ADR 0006: AI domain service boundaries](08-decisions/0006-ai-domain-service-boundaries.md)

## Current delivery boundary

Sprints 1–3 are complete. WO-004A1 adds tenant-isolated AI job and versioned artefact persistence pinned to meeting/transcript versions. WO-004A2 adds internal tenant-scoped repositories, idempotent job creation, explicit lifecycle policy, strict infrastructure-test artefact validation and metadata-only audit events. There is no AI execution, worker, provider, prompt, AI API, AI UI or real intelligence feature. Assistant remains a placeholder. Recording, media storage, transcription, external integrations, production Clerk verification, billing and mobile are not implemented.

Do not use production customer data. Production identity, consent evidence, retention/export/erasure and operational controls are incomplete. Future sprints remain unauthorised until a separate work order is approved.
