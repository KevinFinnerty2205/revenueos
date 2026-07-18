# Product overview

## Product definition

RevenueOS AI is a multi-tenant relationship-intelligence platform. Sales Brain will help relationship-driven revenue professionals prepare for conversations, capture useful context, reduce administration and follow through thoughtfully.

## Target Sales Brain journey

A user will be able to sign in, work within an organisation, manage relationship records, deliberately supply a meeting recording or transcript, review source-linked intelligence, confirm useful memory, prepare follow-up and ask evidence-scoped questions.

These are target product goals, not current capabilities. The complete scope and release boundaries are in the [master product blueprint](master-product-blueprint.md) and [MVP and beta scope](../06-roadmap/mvp-and-beta-scope.md).

## Current product surface

Sprints 1–3 provide:

- an honest public landing page;
- sign-in, sign-up and sign-out paths prepared for Clerk;
- a protected application shell and fixed development organisation;
- Dashboard, Companies, Contacts, Opportunities, Meetings, Tasks, Assistant and Settings navigation;
- a dashboard with polished empty sections;
- tenant-isolated list/create/edit/delete workflows for companies, contacts, opportunities and tasks;
- tenant-isolated meeting, participant and deliberately supplied plain-text transcript workflows with local audit history; and
- a Meeting Detail Intelligence tab that independently queues and displays a transcript-grounded Executive Summary, strict Decisions list, concrete Action Items list and structured Risks & Blockers list through the configured mock or OpenAI provider;
- an Assistant placeholder that states its capability is not implemented.

The current product accepts only deliberately entered meeting metadata and plain-text transcripts. The default provider is a deterministic no-network mock; an explicitly configured server-side OpenAI adapter can process Executive Summary, Decisions, Action Items and Risks & Blockers and sends the selected transcript externally. The application does not record, store media, transcribe, connect external systems, verify production Clerk sessions or process payments. Production customer data must not be used.

## Product principles

- Human judgement remains accountable.
- Evidence and uncertainty are visible.
- Capture is deliberate and consent-aware.
- Customer content is confidential and tenant-isolated.
- Mocks are clearly labelled and never presented as live.
- Shared platform foundations support future products without pre-building them.
