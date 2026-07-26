# ADR 0026: evolve Meeting Intelligence into an Interaction Intelligence platform

## Status

Accepted as target architecture — WO-010, 26 July 2026. Implementation requires
separate approved work orders.

## Context

RevenueOS currently converts deliberately supplied plain-text Meeting transcripts
into validated Meeting Intelligence, Opportunity Workspace views and immutable
Revenue Brain snapshots/changes. This is a strong foundation but does not solve the
most common face-to-face conditions: recording may be refused, inappropriate or
technically unreliable; a salesperson cannot continuously type; and the most useful
recollection decays quickly after the interaction.

The product must prepare for, capture evidence from, understand and support action
after meetings, presentations, workshops, site visits, lunches, calls, conferences,
documents and emails without destabilising the existing tenant-safe Meeting system
or implying that every capture activity is a customer interaction.

## Decision

1. **Interaction is the target logical parent of Meeting.** It owns the generic
   customer-event lifecycle, type, time and relationship context. Meeting remains a
   subtype aggregate with its current IDs, tables, APIs and specialised behaviour
   during an additive migration.
2. **Migration is additive.** Use a tenant-safe one-to-one compatibility relation,
   idempotent new-write creation, bounded historical backfill, adapters and staged
   reads. Do not rename every Meeting table/API or rewrite artefacts/snapshots.
3. **Capture Session is separate from Interaction.** Recording, AI Debrief, Voice
   Journal, visual capture and uploads are bounded acquisition attempts. Failure or
   refusal does not make the Interaction fail.
4. **AI Debrief is a Capture Session and source of reported evidence.** It is not a
   customer Interaction.
5. **Voice Journal is a Capture Session and reported Evidence source.** It appears as
   internal capture activity beneath its Interaction, not another customer event.
6. **Visual Capture belongs to Evidence.** Images and their typed regions/OCR are
   linked to an Interaction/Capture Session; they are not columns on Interaction.
7. **Evidence is source-neutral and versioned.** Recording, transcript, segment,
   visual, document, email, metadata and user observation use a common envelope plus
   typed details/fragments and explicit source-to-derived lineage.
8. **Provenance uses separate explainable axes.** Preserve origin, support,
   validation and freshness instead of one arbitrary confidence percentage.
9. **User verification does not change origin.** Confirming a seller recollection
   strengthens its validation but never makes it direct/customer-confirmed evidence.
10. **Contradictions remain first-class.** Newest or most plausible does not
    automatically win; use source authority, explicit supersession and review.
11. **Current AI artefacts stay immutable.** New source-neutral Interaction
    Intelligence references Interaction and evidence-set versions; an adapter can
    surface existing Meeting artefacts without copying or relabelling their origin.
12. **Revenue Brain evolves by schema version, not rewrite.** Historical Meeting
    snapshots/insights stay unchanged. Later Interaction snapshots reference
    validated structured intelligence and provenance and avoid repeated raw-source
    processing.
13. **The first workflow is a prepared, non-recording face-to-face office meeting
    followed by immediate AI Debrief/Voice Journal.** This validates usefulness and
    trust before recording complexity.
14. **Responsive web is first for brief/debrief; native follows for reliable long
    capture.** A PWA may add convenience but is not a reliable background-recorder
    promise. A cross-platform native client requires a platform spike.
15. **Online capture begins with platform-provided or user-operated import.** Add one
    selected native platform integration based on design partners. Bots are not the
    default first architecture.
16. **Recording starts batch-first.** Use chunk manifests, direct private object
    storage upload, PostgreSQL state and the existing durable worker/provider ports.
    Real-time transport is introduced only for a validated live use case.
17. **The modular monolith remains the system boundary.** No microservice, Redis,
    broker or extra datastore is justified for the first Interaction stages.
18. **Provisional live intelligence cannot become final implicitly.** It is visibly
    provisional, cannot update Revenue Brain or authorise action, and is reconciled
    after final evidence.
19. **Consequential actions remain reviewable.** External communications and system
    writes require current, content/version/destination-bound approval by default.
20. **Privacy and consent are workflow state.** Non-recording fallback, policy,
    notice/consent evidence, source access, retention, deletion, residency and device
    loss are designed into every capture mode; customer legal review is required.

## Consequences

### Positive

- Face-to-face value can arrive before recording, transcription or native mobile.
- Existing Meeting, Workspace and Revenue Brain behaviour remains stable and
  rollback-friendly.
- One evidence/provenance model supports audio, recollection, visuals, documents and
  external sources without hiding their differences.
- The product can explain uncertainty and conflict instead of creating false
  certainty.
- Existing PostgreSQL, worker and provider boundaries cover the first stages.
- Native/real-time infrastructure is gated by observed reliability and user value.

### Costs and constraints

- Compatibility adapters and schema-version bridges add temporary complexity.
- Product/UI language must consistently preserve origin and validation distinctions.
- Deletion requires dependency lineage across storage, evidence, artefacts, memory
  and actions.
- Mobile recording still needs platform-specific engineering, testing and store
  review.
- Each connector/provider adds consent, residency, permission, deletion and
  operational work.
- Cross-version longitudinal reasoning needs an explicit normalised projection before
  old/new snapshots can be compared.

## Alternatives considered

### Rename Meeting to Interaction immediately

Rejected. It couples mature tables, APIs, artefacts, UI and immutable Revenue Brain
history into a high-risk migration with little first-user value.

### Keep Interaction permanently adjacent to Meeting

Rejected. It would create two timelines and duplicated intelligence/memory. The
temporary physical adjacency exists only to reach the logical parent safely.

### Model debriefs, journals, documents and every email as Interactions

Rejected. It confuses customer events with internal capture and floods the timeline.
Only a meaningful customer-facing digital exchange may be an Interaction; its files,
messages and internal debrief remain Evidence/Capture Sessions.

### Recording-first or meeting-bot-first MVP

Rejected. It does not solve refusal, enterprise bans, mobile failure or inappropriate
settings and delays validation of the core evidence/review experience.

### Native app before responsive debrief

Rejected. The first debrief value can be tested in responsive web. Native is
justified by background/offline recording needs after the API and product loop exist.

### One global confidence score

Rejected. Origin, corroboration, verification, freshness, transcription quality and
speaker identity measure different things and cannot be responsibly collapsed.

### Streaming/microservices/message broker from the start

Rejected. Batch post-interaction processing and the current durable worker meet the
first stages. Measured load/latency may justify a later decision.

## Implementation constraints

Future work orders must:

- preserve Meeting and historical Revenue Brain compatibility;
- use Pydantic/OpenAPI as API source of truth and Alembic for schema;
- apply tenant predicates, composite tenant keys and forced RLS;
- keep raw customer content out of logs/audits;
- use deterministic mocks and explicit provider adapters;
- define lifecycle/idempotency/deletion/rollback before adding a source;
- include accessible loading/empty/partial/failure/review states;
- validate privacy/consent with customer legal and security owners; and
- stop at the work order's approved source types and capabilities.

## Related documents

- [Interaction Intelligence vision](../01-product/interaction-intelligence-vision.md)
- [Interaction domain architecture](../03-engineering/interaction-domain-architecture.md)
- [Evidence and provenance model](../03-engineering/evidence-and-provenance-model.md)
- [Interaction Intelligence migration strategy](../03-engineering/interaction-intelligence-migration-strategy.md)
- [Interaction Intelligence roadmap](../06-roadmap/interaction-intelligence-roadmap.md)
