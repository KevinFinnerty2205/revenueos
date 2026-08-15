# Product overview

## Product definition

RevenueOS AI is a multi-tenant relationship-intelligence platform. Sales Brain will help relationship-driven revenue professionals prepare for conversations, capture useful context, reduce administration and follow through thoughtfully.

## Target Sales Brain journey

A user will be able to sign in, work within an organisation, manage relationship
records, prepare for an online or face-to-face interaction, capture the best
available authorised evidence, complete an immediate Voice Journal or targeted AI
Debrief, review source-aware intelligence, confirm useful memory, prepare follow-up
and ask evidence-scoped questions. Recording and transcript import remain optional
capture paths rather than prerequisites.

These are target product goals, not current capabilities. The complete direction is
in the [master product blueprint](master-product-blueprint.md),
[Interaction Intelligence vision](interaction-intelligence-vision.md),
[Interaction Intelligence product blueprint](interaction-intelligence-product-blueprint.md)
and [roadmap](../06-roadmap/interaction-intelligence-roadmap.md).

## Interaction Intelligence direction

RevenueOS is positioned as **the AI operating system for customer interactions**.
The product works across Capture, Intelligence and Action before, during and after
the event. Interaction becomes the future source-neutral parent while the mature
Meeting domain remains compatible through an additive migration. WO-011 now
implements that Interaction identity, Meeting compatibility link and a metadata-only
Evidence/Capture Session foundation. WO-013 now executes AI Debrief and Voice
Journal as supporting capture sessions that produce reviewed reported evidence;
they are not customer interactions. WO-015 adds optional explicitly consented
Recording Capture Sessions and final batch transcripts; it does not make recording
mandatory.

## Current product surface

The current implementation provides:

- an honest public landing page;
- sign-in, sign-up and sign-out paths prepared for Clerk;
- a protected application shell and fixed development organisation;
- Dashboard, Companies, Contacts, Opportunities, Meetings, Tasks, Assistant and Settings navigation;
- a dashboard with polished empty sections;
- tenant-isolated list/create/edit/delete workflows for companies, contacts, opportunities and tasks;
- tenant-isolated meeting, participant and deliberately supplied plain-text transcript workflows with local audit history;
- a unified Meeting Detail Intelligence workspace that derives safe overall state and progress while independently persisting a transcript-grounded Executive Summary, Buying Signals & Deal Momentum, Objections & Competitive Signals, cautious Stakeholder Intelligence, strict Key Decisions, concrete Action Items, structured Risks & Blockers, genuinely unresolved Open Questions and an artefact-only Follow-up Email;
- an [Opportunity Workspace](../03-engineering/opportunity-workspace.md) with
  tenant-safe metadata, meeting association, enriched list previews and the
  latest associated meeting's stored validated intelligence;
- a [Revenue Brain](../03-engineering/revenue-brain-reasoning.md) account
  timeline of immutable snapshots plus deterministic, evidence-backed account
  and opportunity changes across adjacent eligible meetings;
- a controlled private-beta foundation with Clerk organisation sign-in,
  versioned transcript/data notice, onboarding, retention, export/deletion
  requests, usage limits, feedback and an admin-only organisation view; and
- an Assistant placeholder that states its capability is not implemented;
- a tenant-isolated Interaction list/create/detail path with controlled types and
  lifecycle, plus stable bidirectional links to existing Meetings; and
- preparation-only AI Companion briefs for all ten Interaction types, with
  source-aware deterministic composition, readiness, history and optional review;
  and
- completed-Interaction AI Debrief and foreground Voice Journal with typed fallback,
  context-aware bounded questions, mandatory candidate review and visibly
  salesperson-reported Opportunity Workspace/Revenue Brain updates; and
- Capture Session and Evidence foundations with explicit origin, support and
  validation classification. Debrief text is deliberately supplied; raw voice audio
  is never stored.
- optional foreground browser recording with explicit participant notice/authority,
  resumable private WebM/MP4 chunks, durable batch transcription, immutable
  transcript versions/segments and Debrief fallback. All recording flags default
  off.

The current product accepts only deliberately entered meeting metadata and
plain-text transcripts. The default provider is a deterministic no-network
mock; an explicitly configured server-side OpenAI adapter can process Executive
Summary, Buying Signals, Objections & Competitive Signals, Stakeholder
Intelligence, Decisions, Action Items, Risks & Blockers and Open Questions and
sends the selected transcript externally. Buying Signals reports qualitative
current-meeting momentum, Objections reports qualitative current-meeting
pressure and Stakeholder Intelligence reports cautious roles and coverage from
one meeting; none is a win probability, forecast or deal score. The Opportunity
Workspace reads stored artefacts only and neither reads transcripts nor triggers
Meeting Intelligence generation. Revenue Brain reasoning is an explicit
on-demand, provider-free comparison of stored snapshot references: it reports
qualitative supported changes, never probability, forecast or deal health. The
Pre-Interaction Brief is likewise provider-free and reads only validated
structured intelligence plus linked record metadata; it never reads transcript
text. Source completeness is not a success forecast. The
application does not answer or assign customer questions, connect external systems
or process payments. It can record an explicitly armed supported-browser
Interaction and privately retain bounded audio for batch transcription; it never
records implicitly and does not guarantee background/screen-lock capture. It also
transcribes bounded, deliberately submitted post-interaction voice segments.
Production customer data remains prohibited unless separately approved. See the
[private beta readiness guide](../03-engineering/private-beta-readiness.md).

## Product principles

### WO-014 visual evidence boundary

The current browser product accepts deliberately supplied JPEG/PNG evidence on
an Interaction, shows a local preview before confirmation, stores sanitised
bytes privately and requires review of every AI-suggested item. Presentation
Mode keeps seller-created slides as context, business cards as unsaved contact
candidates and site photos as observations. Reviewed eligible evidence appears
in Opportunity Workspace and Revenue Brain with source labels. This remains
separate from WO-015 recording and is not video, native mobile or general document
ingestion.

- Human judgement remains accountable.
- Evidence and uncertainty are visible.
- Capture is deliberate and consent-aware.
- Recording is optional and non-recording face-to-face capture is first-class.
- Salesperson-reported information is never presented as customer-confirmed fact.
- Preparation begins before the interaction and capture occurs while memory is fresh.
- Customer content is confidential and tenant-isolated.
- Mocks are clearly labelled and never presented as live.
- Shared platform foundations support future products without pre-building them.
