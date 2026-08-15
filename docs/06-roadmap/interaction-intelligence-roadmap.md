# Interaction Intelligence roadmap

The current baseline now includes WO-020 bounded Live Interaction Intelligence.
WO-018 already provides recording/transcript import and Debrief fallback for
online meetings. Any native mailbox, drive or meeting adapter remains a separately
approved, design-partner-driven increment.

- **Status:** Recommended sequence; each stage requires a separate approved work
  order before implementation
- **Current baseline:** Work through WO-020 Live Interaction Intelligence is complete;
  WO-010 remains the approved blueprint
- **Primary optimisation:** Earliest trustworthy use for real face-to-face sales
  interactions without requiring recording or transcript upload

## Sequence recommendation

```mermaid
flowchart LR
    A["WO-011: Interaction foundation"] --> B["WO-012: Companion brief"]
    B --> C["WO-013: Debrief and Voice Journal"]
    C --> D["WO-014: Visual evidence"]
    D --> E["WO-015: Recording and transcription"]
    E --> F["WO-016: Face-to-face mobile"]
    F --> G["WO-017: Phone calls"]
    G --> H["WO-018: Online capture"]
    H --> I["WO-019: Documents and email"]
    I --> J["WO-020: Live intelligence"]
    J --> K["WO-021: Interaction Platform Beta"]
```

The Gantt uses relative sequence only; it is not an estimate. Delivery may overlap
independent validation work, but acceptance dependencies remain.

Recommended delivery order: **WO-011, WO-012, WO-013, WO-014, WO-015, WO-016,
WO-017, WO-018, WO-019, WO-020, WO-021**. Phone calls and deliberate online
meeting import are the implemented browser-first bridge to a future provider adapter.
Document/email evidence precedes live intelligence because multi-source
reconciliation is more valuable and less operationally risky than real-time processing.

## Stage gates

Every stage preserves:

- verified tenant context, explicit organisation predicates, composite tenant keys
  and forced RLS;
- current Meeting IDs/APIs and historical Revenue Brain rows;
- content-free logs and safe errors;
- deliberate capture and approved retention/deletion;
- strict versioned contracts and deterministic lifecycle validation;
- human review before consequential action;
- mock/test paths that require no external credential; and
- a rollback/feature-disable path.

No stage starts merely because the previous code merged. Its user, privacy,
reliability and cost decision signals must be reviewed.

## WO-011 — Interaction Domain Foundation

**Delivery status:** Implemented. See the
[WO-011 sprint record](../07-sprints/wo-011-interaction-domain-foundation.md) and
[implementation guide](../03-engineering/interaction-domain-implementation.md).

### Objective and user value

Introduce the tenant-isolated Interaction, compatibility relation, Capture Session
and source-neutral Evidence foundations needed by later capture modes. Users gain a
single future timeline identity while current Meeting workflows remain unchanged.

### Impacts and dependencies

| Area         | Scope                                                                                                                                                                       |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-010 ADR/model; current Meeting, auth, RLS, audit and retention foundations                                                                                               |
| Data model   | Additive Interaction/taxonomy, one-to-one Meeting compatibility relation, Capture Session/Evidence envelopes and lifecycle metadata; exact schema decided in the work order |
| Backend      | Tenant repositories/services, lifecycle policy, additive APIs/adapters, metadata-only audits and bounded historical backfill                                                |
| Frontend     | Minimal interaction read/create shell or hidden integration fixture; no broad redesign                                                                                      |
| Mobile       | None                                                                                                                                                                        |
| AI           | None; no prompt, schema, provider or job capability                                                                                                                         |
| Privacy      | Source classification/retention/consent references from creation; deletion/export lineage foundation                                                                        |
| Operations   | Migration/backfill metrics, reconciliation, feature disable and rollback                                                                                                    |

### Acceptance criteria

- Existing Meeting CRUD, transcript, Intelligence, Opportunity Workspace and Revenue
  Brain behaviour is unchanged.
- Interaction and link queries are tenant-isolated with forced RLS and composite
  tenant constraints.
- New Meeting-to-Interaction creation and historical backfill are idempotent.
- Capture Session and Evidence schemas reject unknown types/states and invalid time
  relationships; their execution lifecycle remains out of scope.
- Deletion/export behaviour is explicit for new metadata.
- Migration upgrade/downgrade/re-upgrade, old-client compatibility and bounded query
  tests pass.

### Out of scope and testing availability

No recording, transcript processing, AI debrief, visual upload, mobile client,
connectors, generic intelligence or Meeting removal. Internal testing can validate
domain/compatibility; end users do not yet receive the face-to-face loop.

## WO-012 — AI Companion and Pre-Interaction Brief

**Delivery status:** Implemented. See the
[WO-012 sprint record](../07-sprints/wo-012-ai-companion-pre-interaction-brief.md),
[product guide](../01-product/ai-companion-preparation.md) and
[engineering guide](../03-engineering/pre-interaction-brief.md).

### Objective and user value

Deliver an interaction-aware preparation brief from current account, opportunity,
Meeting Intelligence and Revenue Brain context. Users arrive prepared with
commitments, risks, stakeholders, open questions and focused objectives.

### Impacts and dependencies

| Area         | Scope                                                                                                                                  |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-011; existing Opportunity Workspace/Revenue Brain; approved brief evaluation                                                        |
| Data model   | Versioned brief artefact or bounded read composition, objective/question feedback metadata and interaction association                 |
| Backend      | Authorised context assembler, deterministic source selection, explicit generate/read policy and stale-source handling                  |
| Frontend     | Responsive brief with citations, origin/status, loading/empty/error and correction links                                               |
| Mobile       | Responsive one-handed view only                                                                                                        |
| AI           | Prefer deterministic composition for first slice; any generated wording needs separate prompt/schema/provider tests in this work order |
| Privacy      | Minimum context, source access checks, no lock-screen customer content                                                                 |
| Operations   | Brief latency, source misses, feature gate and content-free usage events                                                               |

### Acceptance criteria

- Brief contains only authorised same-tenant current structured intelligence.
- Every factual item has an evidence/artefact link or explicit recommendation label.
- Already resolved/stale items are not presented as current without explanation.
- Type-specific objectives/questions work for meeting and presentation foundations.
- Opening the brief does not mutate Revenue Brain or create actions.
- Accessibility, responsive and no-context/partial/failure states pass.

### Out of scope and testing availability

No debrief, recording, email/document connector, live coaching or external action.
Users can test preparation for real interactions, including without recording.
Existing Meeting Intelligence still depends on deliberately supplied transcripts;
the brief service itself never reads them.

## WO-013 — AI Debrief and Voice Journal

**Implementation status:** Complete. See the
[WO-013 sprint record](../07-sprints/wo-013-ai-debrief-voice-journal.md).

### Objective and user value

Deliver the flagship post-interaction workflow: “Let’s capture this while it is
fresh,” natural voice/text journal, high-value opportunity-aware questions,
provenance-aware review and validated Interaction Intelligence using reported
evidence.

### Impacts and dependencies

| Area         | Scope                                                                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-011/012, current AI provider/job foundations, approved reported-evidence schema/evaluation, launch privacy review                         |
| Data model   | Debrief Capture Session, question/response evidence fragments, claim/provenance/review versions and eligibility for generic intelligence     |
| Backend      | Context/gap policy, session lifecycle, bounded question orchestration, strict extraction/reconciliation and Workspace/Brain integration path |
| Frontend     | Prompt, safe-driving confirmation, foreground voice/text journal, skip/stop/recover, claim review and draft/failure states                   |
| Mobile       | Responsive foreground capture; no locked-screen/background recording promise                                                                 |
| AI           | Versioned structured journal extraction and question intent/wording only under application-owned caps/policy; deterministic mock required    |
| Privacy      | Reported-origin preservation, microphone permission, lock-screen minimisation, retention/deletion and customer-data launch gate              |
| Operations   | Session/question latency, abandonment, unsupported claims, correction, provider cost and content-free telemetry                              |

### Acceptance criteria

- A user completes a real face-to-face flow without recording or transcript upload.
- Questions already answered by authorised context are suppressed.
- Question cap, reason, skip and stop work; interruption preserves a draft.
- Direct, reported and inferred origins cannot be conflated in API or UI.
- No quotation or customer confirmation is created from recollection alone.
- Review/correction/dispute/exclusion invalidate and promote downstream state
  correctly.
- Opportunity Workspace and Revenue Brain consume only eligible validated outputs
  with source references.
- Driving warning/confirmation, accessibility, tenant, deletion, provider-mock and
  content-redaction tests pass.

### Out of scope and testing availability

No long background recording, visual OCR, online bots, live intelligence, autonomous
actions or CRM sync. **This is the earliest stage Kevin can use RevenueOS for real
face-to-face sales meetings without manually uploading a transcript**, but only
after the production customer-data, legal/privacy and operational gates for the
target environment are satisfied.

## WO-014 — Visual Evidence Capture

**Delivery status:** implemented by WO-014, including the Presentation Mode
specialisation, private storage lifecycle and source-aware review described in
the accepted work order. Later work orders remain unauthorised.

### Objective and user value

Allow authorised photos/files such as whiteboards, workshop walls, diagrams,
agendas, business cards and customer requests to support the same Interaction
Intelligence and debrief review.

### Impacts and dependencies

| Area         | Scope                                                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------------------------ |
| Dependencies | WO-011/013, object-storage decision, image/document security review                                                |
| Data model   | Visual Evidence typed detail, image-region fragments, derived OCR/caption versions, classification and lineage     |
| Backend      | Short-lived upload grants or bounded upload, validation/scanning, object storage port, derivative job and deletion |
| Frontend     | Camera/file selection, permission guidance, preview/crop/exclude, upload/retry, extracted-item review              |
| Mobile       | Responsive foreground camera; bounded offline support only if proven                                               |
| AI           | Optional strict OCR/vision extraction behind provider port with deterministic fixture/mock; image remains source   |
| Privacy      | Photo-specific consent, personal/confidential data, metadata minimisation, access and deletion                     |
| Operations   | Storage/orphan cleanup, processing cost/latency, unsupported format and provider failure                           |

### Acceptance criteria

- Visual evidence is tenant-scoped, private, checksummed and linked to Interaction.
- OCR/caption is labelled derived and cites an image region where possible.
- Users can exclude/delete before promotion and correct extracted information.
- Business-card extraction never silently creates a Contact.
- Sensitive/unsupported/partial/upload-failure states are explicit.
- Deletion propagates to source, derivatives, intelligence and provider copies.

### Out of scope and testing availability

No face recognition, protected-attribute inference, bulk document connector, native
background upload or autonomous contact creation. Users can test workshops,
presentations and site visits with foreground visual evidence.

## WO-015 — Recording and Transcription Foundation

**Delivery status:** Implemented by WO-015. The design below remains the accepted
scope record; WO-016 and later work are not authorised by this status.

### Objective and user value

Add optional finalised audio capture/upload and reliable batch transcription as one
evidence source, with resumable chunks, recovery, source alignment and clear partial
states.

### Impacts and dependencies

| Area         | Scope                                                                                                                   |
| ------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-011 evidence model, object storage, selected transcription provider evaluation, consent/security review              |
| Data model   | Recording session/chunk manifest, recording evidence, transcript/segment versions and provider trace                    |
| Backend      | Signed direct upload, finalisation, existing durable worker stages, transcription provider port, bounded retry/deletion |
| Frontend     | Foreground/user-operated capture or file selection, consent, progress, partial/gap, transcript review                   |
| Mobile       | Foreground capture only unless a separate native spike passes; API designed for later client                            |
| AI           | Batch transcription and optional diarisation; no live intelligence                                                      |
| Privacy      | Recording notice/consent, raw-media retention, region/provider, microphone and deletion                                 |
| Operations   | Storage lifecycle, orphan reconciliation, queue/lease, cost/quota, provider and failure runbooks                        |

### Acceptance criteria

- Duplicate/out-of-order chunks are idempotent and checksum conflicts fail safely.
- Complete/partial finalisation and interruption recovery are transparent.
- Batch transcript is versioned and aligned to source; user correction preserves
  history.
- Speaker label is not silently mapped to a Contact.
- Non-recording debrief remains fully usable.
- Duration/size/quota, consent, retention/deletion, provider mock/contract and
  content-free observability pass.

### Out of scope and testing availability

No reliable screen-lock/background mobile recording, streaming transcript, bot,
advanced diarisation or live signal. Selected users can test authorised foreground
or uploaded recordings plus the established debrief fallback.

## WO-016 — Browser Face-to-Face Companion

**Delivery status:** Implemented by WO-016. Native/PWA capture remains a separate,
evidence-led future decision rather than part of this work order.

### Objective and user value

Deliver the smallest coherent browser-first Companion for the full face-to-face
loop: a concise brief before, an intentionally chosen recording or passive mode
during, and immediate evidence-gap capture after the interaction.

### Impacts and dependencies

| Area         | Scope                                                                                                                                 |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-012/013/014/015 brief, debrief, visual-evidence and recording foundations                                                          |
| Data model   | Tenant-isolated metadata-only quick markers with type, creator, interaction time and optional recording offset                        |
| Backend      | Idempotent Interaction start, marker CRUD, recording concurrency protection and capture-status projection                             |
| Frontend     | Responsive `/interactions/{id}/companion` with BEFORE, DURING and AFTER phases; no dense live transcript or coaching                  |
| Mobile       | Foreground browser recording only; bounded retry and recovery, screen wake lock where available, honest screen-lock/background limits |
| AI           | Reuses existing deterministic brief and reviewed debrief; gap prompts suppress targets already covered by direct evidence             |
| Privacy      | Explicit recording/passive choice, consent gate, content-free markers, truthful phone/online limitations and no implicit listening    |
| Operations   | Browser support matrix, safe logs, quota/retention controls, interrupted-session recovery and synthetic end-to-end coverage           |

### Acceptance criteria

- The browser route carries the user through BEFORE, DURING and AFTER without
  creating a second interaction or duplicating the underlying services.
- Recording remains optional, consent-gated and foreground-only; passive mode,
  markers and visual evidence work without microphone access.
- Pending chunks retain stable idempotency keys across bounded retry, and completion
  is blocked while recording or queued upload work remains.
- Phone calls and online meetings never present browser microphone capture as a
  reliable way to capture the same-device call or system audio.
- Metadata-only markers are tenant-isolated, idempotent, soft-deletable and excluded
  from logs; export/deletion/demo maintenance paths include them.
- The AFTER phase exposes capture state, targeted debrief, visual review and links
  back to Opportunity Workspace and Revenue Brain.
- Mobile viewport, keyboard, semantic accessibility and recording/passive paths are
  covered by unit and browser tests.

### Out of scope and testing availability

No native/PWA application, background or screen-lock guarantee, offline media
buffer, live transcript, live coaching, bot, phone interception, reliable online
system-audio capture, push notification or autonomous action. Approved beta users
can test the labelled foreground browser flow with synthetic data and authorised
capture only.

## WO-017 — Phone Call Intelligence

**Delivery status:** Implemented by WO-017. Telephony providers and cellular
interception remain excluded.

Phone calls now use the existing Interaction lifecycle, compact brief, adaptive
reviewed Debrief/Voice Journal and optional authorised recording import. Controlled
direction/outcome, tenant-safe Contact association, timeline readiness and
recording/debrief reconciliation feed the existing Opportunity Workspace and Revenue
Brain without a phone silo. See the
[WO-017 sprint record](../07-sprints/wo-017-phone-call-intelligence.md).

## WO-018 — Online Meeting Capture

**Delivery status:** Implemented by WO-018 with provider-neutral manual import. A
production native adapter remains a separate, design-partner-driven increment.

### Objective and user value

Ingest authorised recording/transcript evidence for Teams, Zoom, Meet or other
online meetings, with AI Debrief/Voice Journal fallback.

### Impacts and dependencies

| Area         | Scope                                                                                                               |
| ------------ | ------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-012 through WO-017; no connector credential required                                                             |
| Data model   | Tenant-owned normalised meeting metadata and transcript-import provenance                                           |
| Backend      | Safe references, capabilities, idempotent TXT/VTT/SRT import, WO-015 recording reuse and deterministic adapter fake |
| Frontend     | Safe open, passive meeting state, capability-driven import and Debrief/Voice Journal fallback                       |
| Mobile       | None required; existing Companion surfaces consume results                                                          |
| AI           | Reuse transcription only when source lacks an approved transcript; no new live capability                           |
| Privacy      | Authority notice, URL/token minimisation, tenant/RLS isolation and local/upstream deletion boundary                 |
| Operations   | Existing recording/transcription quotas, metadata-only state and import retry/deduplication                         |

### Acceptance criteria

- Teams, Zoom, Meet and other use one normalised Interaction workflow.
- User-authorised imports are tenant/version scoped and duplicates are reconciled.
- Missing artefacts and participant ambiguity remain usable, honest states.
- User-operated import and non-recording debrief remain fallbacks.
- No bot is described as working unless separately implemented and visibly tested.

### Out of scope and testing availability

No production Teams/Zoom/Meet connector, calendar-triggered bot, universal browser
audio or live intelligence. All providers use explicit import or Debrief fallback;
Google Meet v2 is only the conditional first technical-spike recommendation.

## WO-019 — Document and Email Evidence

**Delivery status:** Implemented by WO-019 with deliberate PDF/TXT upload and
plain-text email paste. No provider connector was selected: mailbox/drive sync,
DOCX, OCR and attachments remain outside the current boundary.

### Objective and user value

Ingest deliberately selected or narrowly scoped authorised proposals, RFPs,
requirements, pricing, contracts, technical documents and customer emails as
evidence feeding the same claims and relationship timeline.

### Impacts and dependencies

| Area         | Scope                                                                                                                              |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-011/014 evidence model, one selected connector or upload path, source-permission and authority design                           |
| Data model   | Document/email evidence versions, source fields, page/message fragments, external permissions/sync and authoritative-field mapping |
| Backend      | One narrow adapter or selected upload, content extraction, permission recheck, lineage and deletion/revocation                     |
| Frontend     | Select/link/review source, authority/origin badges, conflict and extraction review                                                 |
| Mobile       | View/select where supported; no full mailbox/drive client                                                                          |
| AI           | Strict claim extraction with citations and prompt-injection controls; deterministic mock/evaluation                                |
| Privacy      | Least scopes, third-party/personal data, privileged/confidential documents, provider/residency and source ACL                      |
| Operations   | Connector health, rate limit, access revocation, file bomb/malware/format, cost and deletion                                       |

### Acceptance criteria

- The first source path is deliberate and least-privilege, not blanket collection.
- Every claim cites a page/range/message/field and keeps customer/seller/import origin.
- Prepared proposal claims do not become customer agreement.
- Source permission/revocation is enforced at access and downstream eligibility.
- Conflicts with CRM/interaction evidence are visible, not overwritten.
- Injection, malicious file, tenant, retention/deletion and connector mock tests pass.

### Out of scope and testing availability

No full mailbox/drive ingestion, silent contact creation, contract/legal advice,
automatic CRM write or arbitrary enterprise document coverage. Users can test the
selected source path and multi-source reconciliation.

## WO-020 — Live Interaction Intelligence

**Delivery status:** Implemented by WO-020 as an optional deterministic/no-network
provisional path over an authorised progressive transcript. See the
[sprint record](../07-sprints/wo-020-live-interaction-intelligence.md) and
[product guide](../01-product/live-interaction-intelligence.md).

### Objective and user value

Evaluate and deliver a narrowly scoped, opt-in live capability that identifies
provisional markers such as objections, actions or unanswered questions when doing
so materially improves the interaction or post-interaction review.

### Impacts and dependencies

| Area         | Scope                                                                                                                  |
| ------------ | ---------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-015/016 and validated recording adoption, final-intelligence evaluation, explicit product need and privacy approval |
| Data model   | Provisional transcript/claim versions, coverage/gap and final-reconciliation relation                                  |
| Backend      | Server-authoritative cursor, bounded polled windows, separate provisional state and final reconciliation               |
| Frontend     | Suppressible, non-intrusive provisional UI; final review clearly separate                                              |
| Mobile       | Responsive foreground browser only; no native client or background guarantee                                           |
| AI           | Deterministic no-network extraction for a small allowed taxonomy; external live AI remains off                         |
| Privacy      | Explicit mode/indicator, no covert coaching, consent and provider streaming path                                       |
| Operations   | Stream health, latency, cost, backpressure, partial/final disagreement and feature kill switch                         |

### Acceptance criteria

- User research shows the selected live use case provides value beyond post-session
  processing.
- Every live output is labelled provisional and barred from Revenue Brain/action
  eligibility.
- Final evidence reconciliation can correct/remove live results and explains the
  changed status.
- Interruption, missing chunks, latency and cost limits degrade to normal debrief.
- No default intrusive coaching or employee-monitoring use is introduced.

### Out of scope and testing availability

No broad live coach, emotion analysis, autonomous action, universal platform or
guaranteed real-time result. Only explicitly enabled private-beta workspaces test the
selected provisional use case; production progressive transcription remains unavailable.

## WO-021 — Interaction Platform Beta

### Objective and user value

Harden the proven Interaction lifecycle into a governed beta: preparation,
non-recording debrief, visual evidence, selected recording/mobile/online/document
paths, source-aware intelligence, relationship memory and reviewable action.

### Impacts and dependencies

| Area         | Scope                                                                                                                             |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Dependencies | Proven prior stages selected for beta; WO-009 controls and completed target-environment launch evidence                           |
| Data model   | Stable versioned APIs/schemas, retention/export/deletion coverage, migration/backfill completion and compatibility support window |
| Backend      | Scale/reliability hardening, quotas/entitlements as approved, admin/connection health and incident controls                       |
| Frontend     | Coherent Interaction Timeline, Workspace/Brain, review/action queue, onboarding and accessibility                                 |
| Mobile       | Supported device matrix, store release and operational support for included capture modes                                         |
| AI           | Evaluation gates, model/prompt rollback, cost/latency policy and source-aware safety                                              |
| Privacy      | Customer policy configuration, consent evidence, region/provider inventory, DSR/export/deletion and security review               |
| Operations   | SLOs, monitoring, support, backup/recovery, incident/provider disable, load/cost and beta runbooks                                |

### Acceptance criteria

- Included capture modes have documented support and honest fallback; excluded modes
  are not implied.
- End-to-end tenant, RLS, object-storage, connector and worker security tests pass.
- Provenance, conflict, verification and deletion work across every included source.
- Current Meeting clients/historical snapshots remain available under the documented
  compatibility window.
- Accessibility, mobile matrix, provider/model evaluation, cost/latency and support
  gates pass.
- External actions remain approval-bound and employee-surveillance uses are absent.
- Customer legal/privacy/security approval and target-environment launch checklist
  are complete.

### Out of scope and testing availability

General availability, autonomous external action, every platform/provider, universal
native device support, unrestricted live coaching, forecasting and additional Brain
products remain separate decisions. Approved beta customers can test the complete
supported lifecycle.

## Product validation metrics

Use metrics that test relationship and workflow value:

- interactions prepared and brief opened before the event;
- recording versus non-recording capture adoption;
- debrief start/completion/skip and time from end to first evidence;
- average debrief duration and question answer/skip rate;
- usable intelligence coverage by interaction type/source;
- evidence/claim confirmation, correction, dispute and dismissal;
- visual/document/source adoption where available;
- Revenue Brain updates with valid provenance;
- accepted follow-up/actions and measured time saved; and
- repeated use of prior validated intelligence in later preparation.

Avoid raw model activity, recording hours and individual rankings. Review metrics by
workflow and source to find trust/reliability problems without surveilling sellers.

## Stop or change criteria

Pause a stage when:

- the preceding simpler workflow does not show repeated user value;
- provenance correction or unsupported-claim rates breach its gate;
- consent, residency or enterprise policy blocks the target cohort;
- capture reliability or cost makes usable intelligence uneconomic;
- user questioning/notifications harm trust; or
- the stage requires new infrastructure without measured need.

Choose the fallback already built—brief, debrief, user-operated import or manual
review—before broadening architecture.

## Related documents

- [Interaction Intelligence product blueprint](../01-product/interaction-intelligence-product-blueprint.md)
- [Interaction platform risk register](../03-engineering/interaction-platform-risk-register.md)
- [Interaction Intelligence migration strategy](../03-engineering/interaction-intelligence-migration-strategy.md)
- [WO-010 sprint record](../07-sprints/wo-010-interaction-intelligence-blueprint.md)

## Implemented Action milestone

WO-021 implements the review-only Action Layer: typed proposals, immutable revisions,
human approval/rejection, internal manual completion, Opportunity Workspace review
and brief feedback. External execution, connectors and autonomous workflows remain
future work and require a separate approved work order.
