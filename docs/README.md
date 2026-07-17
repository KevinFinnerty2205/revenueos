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

## 08 — Decision records

- [ADR 0001: foundation architecture](08-decisions/0001-foundation-architecture.md)
- [ADR 0002: tenant-owned business entities](08-decisions/0002-tenant-business-entities.md)
- [ADR 0003: product blueprint and beta sequencing](08-decisions/0003-product-blueprint-and-beta-sequencing.md)

## Current delivery boundary

Sprint 1 and Sprint 2 are complete. The repository currently implements the web/API foundation and tenant-isolated companies, contacts, opportunities and tasks. Meetings and Assistant are placeholders. Recording, transcripts, AI, external integrations, production Clerk verification, billing and mobile are not implemented.

The recommended next implementation sprint is [Sprint 3: Meeting Domain Foundation](06-roadmap/product-roadmap-to-beta.md). It does not begin as part of the blueprint documentation work.
