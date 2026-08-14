# Interaction Intelligence roadmap

- **Status:** Recommended sequence; each stage requires a separate approved work
  order before implementation
- **Current baseline:** Work through WO-014 is complete; WO-010 is the approved blueprint
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
    F --> G["WO-017: Online capture"]
    G --> H["WO-019: Documents and email"]
    H --> I["WO-018: Live intelligence"]
    I --> J["WO-020: Interaction Platform Beta"]
```

The Gantt uses relative sequence only; it is not an estimate. Delivery may overlap
independent validation work, but acceptance dependencies remain.

Recommended delivery order: **WO-011, WO-012, WO-013, WO-014, WO-015, WO-016,
WO-017, WO-019, WO-018, WO-020**. Document/email evidence precedes live intelligence
because multi-source reconciliation is more valuable and less operationally risky
than real-time processing. WO-017 and WO-019 may swap based on design-partner needs.

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

## WO-016 — Face-to-Face Mobile Capture

### Objective and user value

Provide a constrained cross-platform native companion for reliable long face-to-face
recording, offline encrypted buffering, screen lock, interruptions, visual capture
and push-triggered debrief.

### Impacts and dependencies

| Area         | Scope                                                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------------------------ |
| Dependencies | WO-013/014/015, successful framework/platform spike, mobile threat model and store-policy review                   |
| Data model   | Device/client metadata class, push token reference, local/server sync state and revoke/delete receipts             |
| Backend      | Mobile session/auth, background transfer, sync reconciliation, push trigger and device revocation                  |
| Frontend     | Existing web review remains; shared contracts/design system where useful                                           |
| Mobile       | Native audio session, encrypted chunks, offline queue, calls/lock/battery/storage/Bluetooth, camera, accessibility |
| AI           | No new intelligence requirement; consumes recording/debrief paths                                                  |
| Privacy      | OS permission/indicator, offline loss, notification privacy, MDM/shared responsibility, store disclosures          |
| Operations   | Device matrix, crash/sync diagnostics without content, store release, compatibility and revoke runbooks            |

### Acceptance criteria

- Platform matrix passes long sessions, screen lock, calls, OS termination, restart,
  battery/storage/network and Bluetooth cases.
- Local evidence is encrypted, quota-bound and deleted after verified upload/policy.
- Partial/gap/upload states are honest and debrief fallback works.
- Push is optional, deduplicated, quiet-hour aware and content-free.
- Accessibility and store/privacy requirements are verified against current policy.
- Lost-device revocation and next-contact deletion are tested without a false remote
  wipe claim.

### Out of scope and testing availability

No live coaching, universal device support, guaranteed offline remote wipe or desktop
capture. Approved pilot users can test reliable face-to-face mobile capture within
the supported device/policy matrix.

## WO-017 — Online Meeting Capture

### Objective and user value

Ingest authorised recording/transcript and attendance context from the selected
design-partner online meeting platform, with user-operated import as fallback.

### Impacts and dependencies

| Area         | Scope                                                                                                                      |
| ------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Dependencies | WO-015, selected platform/customer stack, connector/auth foundation and platform policy review                             |
| Data model   | Tenant connection/external identity, meeting asset/version, sync cursor/state, participant candidates and deletion receipt |
| Backend      | One native platform adapter or platform-provided import, webhook/poll reconciliation, idempotent ingest and auth health    |
| Frontend     | Connect/select/import, capture visibility, match/review and failure recovery                                               |
| Mobile       | None required; existing Companion surfaces consume results                                                                 |
| AI           | Reuse transcription only when source lacks an approved transcript; no new live capability                                  |
| Privacy      | Least scopes, participant notice, platform indicator, region/retention and revocation                                      |
| Operations   | Token/webhook health, rate limits, waiting/processing delay, duplicate/deletion runbooks                                   |

### Acceptance criteria

- One selected platform works end to end with deterministic mocks and real sandbox or
  approved test evidence.
- External objects are tenant/version scoped and duplicates are reconciled.
- Platform/user deletion and auth revocation propagate.
- Missing recording, delayed transcript, participant mismatch and partial source are
  usable states.
- User-operated import and non-recording debrief remain fallbacks.
- No bot is described as working unless separately implemented and visibly tested.

### Out of scope and testing availability

No universal Zoom/Teams/Meet support, calendar-triggered bot, browser-only universal
audio or live intelligence. Users on the selected platform can test automated or
explicit import; others retain manual/debrief paths.

## WO-019 — Document and Email Evidence

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

## WO-018 — Live Interaction Intelligence

### Objective and user value

Evaluate and deliver a narrowly scoped, opt-in live capability that identifies
provisional markers such as objections, actions or unanswered questions when doing
so materially improves the interaction or post-interaction review.

### Impacts and dependencies

| Area         | Scope                                                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Dependencies | WO-015/016 and validated recording adoption, final-intelligence evaluation, explicit product need and privacy approval   |
| Data model   | Provisional transcript/claim versions, coverage/gap and final-reconciliation relation                                    |
| Backend      | Streaming/near-real-time transport only for selected use case, bounded buffers, provisional state and final reprocessing |
| Frontend     | Suppressible, non-intrusive provisional UI; final review clearly separate                                                |
| Mobile       | Supported native capture path only; battery/network behaviour tested                                                     |
| AI           | Evaluated live extraction for a small allowed taxonomy; strict provisional output                                        |
| Privacy      | Explicit mode/indicator, no covert coaching, consent and provider streaming path                                         |
| Operations   | Stream health, latency, cost, backpressure, partial/final disagreement and feature kill switch                           |

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
guaranteed real-time result. Only explicit pilot users test the selected provisional
use case.

## WO-020 — Interaction Platform Beta

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
