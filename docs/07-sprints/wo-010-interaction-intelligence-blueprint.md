# WO-010 — Interaction Intelligence Blueprint

## Status

Documentation and architecture completed on
`docs/wo-010-interaction-intelligence-blueprint`. WO-010 implements no product code,
schema, migration, dependency, AI capability or application behaviour.

## Product direction

RevenueOS is positioned as **the AI operating system for customer interactions**.
Its north star is:

> RevenueOS captures the best possible evidence from every customer interaction,
> transforms that evidence into trusted intelligence, and helps sales teams build
> stronger customer relationships over time.

The product spans Capture, Intelligence and Action and supports preparation,
optional/passive during-interaction capture and immediate post-interaction debrief.
Recording is optional and never the only path.

## Architecture decisions

- Interaction becomes the logical parent for future customer events; Meeting remains
  a compatible subtype through an additive migration.
- Existing Meeting IDs, APIs, intelligence artefacts, Opportunity Workspace and
  historical Revenue Brain records remain unchanged.
- AI Debrief and Voice Journal are Capture Sessions producing
  salesperson-reported evidence, not customer Interactions.
- Visual Capture is source-neutral Evidence with typed fragments and derived
  representations.
- Provenance preserves origin, support, validation and freshness separately; user
  confirmation never changes origin.
- Contradictory evidence remains visible until resolved by authority, explicit
  supersession or review.
- Revenue Brain evolves through new snapshot versions and validated structured
  references rather than repeated raw-source processing or historical rewrite.
- The modular monolith, PostgreSQL durable worker and provider ports remain the
  foundation; real-time/mobile infrastructure is added only when justified.

The accepted decision is [ADR 0026](../08-decisions/0026-interaction-intelligence-platform.md).

## Face-to-face MVP

Build a standard non-recording customer office meeting first:

1. opportunity-aware preparation brief;
2. passive interaction with optional capture;
3. prompt “Let’s capture this while it is fresh”;
4. safe natural Voice Journal and targeted AI Debrief;
5. source-aware claim review;
6. validated Interaction Intelligence;
7. Opportunity Workspace and Revenue Brain update; and
8. reviewable follow-up/actions.

Kevin can begin using this flow for real face-to-face meetings without manual
transcript upload after WO-013, subject to its acceptance criteria and the target
environment's production-customer-data, legal/privacy and operational launch gates.

## Recommended delivery sequence

1. WO-011 — Interaction Domain Foundation
2. WO-012 — AI Companion and Pre-Interaction Brief
3. WO-013 — AI Debrief and Voice Journal
4. WO-014 — Visual Evidence Capture
5. WO-015 — Recording and Transcription Foundation
6. WO-016 — Face-to-Face Mobile Capture
7. WO-017 — Online Meeting Capture
8. WO-019 — Document and Email Evidence
9. WO-018 — Live Interaction Intelligence
10. WO-020 — Interaction Platform Beta

No implementation stage is authorised by this record. See the
[Interaction Intelligence roadmap](../06-roadmap/interaction-intelligence-roadmap.md)
for scope, impacts, acceptance criteria and explicit exclusions.

## Documentation delivered

### Product

- [Interaction Intelligence vision](../01-product/interaction-intelligence-vision.md)
- [Interaction Intelligence product blueprint](../01-product/interaction-intelligence-product-blueprint.md)

### Design

- [Interaction lifecycle and UX](../02-design/interaction-lifecycle-and-ux.md)
- [Face-to-face interaction experience](../02-design/face-to-face-interaction-experience.md)
- [AI Companion and debrief](../02-design/ai-companion-and-debrief.md)
- [Presentation mode](../02-design/presentation-mode.md)
- [Mobile companion strategy](../02-design/mobile-companion-strategy.md)

### Engineering

- [Interaction domain architecture](../03-engineering/interaction-domain-architecture.md)
- [Evidence and provenance model](../03-engineering/evidence-and-provenance-model.md)
- [Recording and transcription architecture](../03-engineering/recording-and-transcription-architecture.md)
- [Interaction Intelligence migration strategy](../03-engineering/interaction-intelligence-migration-strategy.md)
- [Interaction security, privacy and consent](../03-engineering/interaction-security-privacy-and-consent.md)
- [Interaction platform risk register](../03-engineering/interaction-platform-risk-register.md)

### Roadmap and decision

- [Interaction Intelligence roadmap](../06-roadmap/interaction-intelligence-roadmap.md)
- [ADR 0026](../08-decisions/0026-interaction-intelligence-platform.md)

Canonical existing product, architecture, AI, Opportunity Workspace, Revenue Brain,
roadmap, repository and documentation-index pages link to this target direction
without describing it as implemented.

## Explicit exclusions

- product/API/UI/mobile implementation;
- database migrations or schema changes;
- dependencies or lockfile changes;
- AI prompts, schemas, jobs, providers or service types;
- recording, object storage or transcription;
- integration, bot, connector or live intelligence;
- feature flags or application behaviour;
- legal conclusions; and
- merge or deployment.

## Validation boundary

WO-010 validation checks Markdown formatting/links, Mermaid syntax, documentation
consistency and Git scope. Repository diff verification must confirm no production
source, migration, manifest or lockfile change. The current code gate does not need
to run solely because prose changed unless repository formatting/audit tooling
requires it; the exact commands run are reported in the pull request.

## Unresolved implementation decisions

- physical Meeting-to-Interaction link shape and backfill batch design;
- exact Interaction/Evidence API contracts and registry/state enums;
- evaluated debrief model/provider, question cap and promotion thresholds;
- first object storage/transcription provider and residency path;
- first supported mobile framework/device matrix;
- first online platform/connector based on design-partner stack;
- cross-version Revenue Brain normalised projection;
- customer/jurisdiction consent configuration; and
- evidence-strength language validated with users.
