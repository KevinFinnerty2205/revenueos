# AI system blueprint

**Status:** Target architecture through private beta; no AI capability is implemented by this document.

The AI system extends the existing modular monolith and provider-port architecture. FastAPI handles bounded requests, durable database-backed jobs handle long work, and Pydantic/OpenAPI contracts remain canonical. It does not introduce autonomous agents, implicit tools or an additional distributed system.

## System boundary

```text
Authorised source
  → Conversation Intelligence Engine
  → reviewable AI artifacts
  → Relationship Memory Engine
  → authorised retrieval context
  → AI Reasoning Engine
  → Workflow Engine proposals
  → human approval
  → Integration Layer execution
```

The pipeline is not automatically linear. A user may stop, correct, exclude or delete at every review boundary. No engine gains permissions merely because another engine produced output.

## 1. Conversation Intelligence Engine

- **Responsibilities:** Transcription orchestration, speaker/participant assistance, meeting segmentation, source-backed summary, commitments, next-step candidates and CRM-relevant fact candidates.
- **Inputs:** Authorised recording or transcript, meeting metadata, user-confirmed participant/account links and organisation policy.
- **Outputs:** Versioned transcript/segments and structured `AIArtifact` records with source spans, confidence metadata and prompt/model versions.
- **Storage boundaries:** Raw files stay in private object storage; transcript and derived data stay in tenant-owned PostgreSQL records; provider request data is not an application system of record.
- **Confidence handling:** Confidence is component-specific—transcription, speaker, match and claim confidence are not collapsed into one score. Below-threshold output enters review or failure, never silent promotion.
- **Human review:** Required for participant/account matching when uncertain and for all meeting intelligence before it creates accountable work, memory or external proposals in the pilot.
- **Failure behaviour:** Retain completed stages; label partial output; classify retryable provider failure separately from unsupported/unsafe input; never invent missing transcript text.
- **Observability:** Stage duration, input duration/size, provider/model identifier, token/audio usage, retry class, confidence distribution, correction rate and completion outcome. No raw transcript in logs.
- **Pilot/Beta scope:** Manual upload/paste, one bounded transcription path, structured summary and next steps with citations.
- **Future scope:** Additional languages, diarisation options, provider routing and domain-specific extraction for Recruitment/Customer Success after separate evaluation.

## 2. Relationship Memory Engine

- **Responsibilities:** Convert reviewed evidence into concise memory candidates; link sources; detect conflict/staleness; retrieve authorised memory for briefings; process correction, supersession and deletion.
- **Inputs:** User-confirmed meeting artefacts, authoritative connected records, relationship events, correction history and policy.
- **Outputs:** Versioned `MemoryItem`/`MemorySource` records, conflict indicators, staleness state and ranked authorised retrieval results.
- **Storage boundaries:** Memory and provenance remain tenant-owned. Embeddings, if introduced, are tenant-scoped indexes and never the source of truth.
- **Confidence handling:** Track evidence strength, source authority, recency and confirmation separately. User-confirmed correction outranks an older model inference.
- **Human review:** Required for sensitive, consequential, conflicting or low-confidence memory; policy may permit narrow low-risk confirmed facts after evaluation.
- **Failure behaviour:** Insufficient evidence yields no memory; conflict remains visible; deleted/excluded sources are immediately removed from retrieval and queued for downstream cleanup.
- **Observability:** Candidate acceptance/edit/rejection, citation coverage, stale/superseded rate, retrieval usefulness, correction propagation and deletion completion.
- **Pilot/Beta scope:** Source-backed commitments, preferences, risks and decisions; correction/deletion; meeting-preparation retrieval.
- **Future scope:** Cross-product memory policies only after product-specific privacy and ontology review.

## 3. Workflow Engine

- **Responsibilities:** Turn reviewed intelligence into bounded suggested actions, approvals, tasks and durable execution state; enforce leases, retries, idempotency and expiry.
- **Inputs:** Reviewed artefacts, policy, authoritative record snapshots, connection capabilities and user intent.
- **Outputs:** `SuggestedAction`, `Approval`, internal task and `SyncOperation` state; notifications for exceptions.
- **Storage boundaries:** Action content and execution metadata are tenant-owned; secrets remain in a secret manager/token vault; provider receipts store only necessary identifiers.
- **Confidence handling:** Confidence affects whether an action may be proposed and its review priority. It never authorises execution.
- **Human review:** Every external communication and CRM write requires a specific, current user approval during beta. AI-created accountable tasks also require acceptance.
- **Failure behaviour:** Expired/stale approvals fail closed; ambiguous external results reconcile before retry; permanent failures return to an exception queue.
- **Observability:** Proposal-to-approval time, edit/reject rates, approval actor, execution latency, retry class, reconciliation outcome and duplicate-prevention signal.
- **Pilot/Beta scope:** Follow-up draft, task and CRM field proposals; approval centre; one supported adapter path at a time.
- **Future scope:** Policy-based batches and low-risk automation only after separate product approval, safety evidence and reversible controls.

## 4. AI Reasoning Engine

- **Responsibilities:** Compose source-grounded account answers, meeting briefs, changed-context explanations and suggested questions from authorised retrieval.
- **Inputs:** Explicit user question or briefing request, current user/tenant context, ranked authorised evidence and product-specific instruction template.
- **Outputs:** Structured answer/brief with claims, citations, uncertainty, conflicts and unsupported areas.
- **Storage boundaries:** Store only artefacts needed for audit/product value; prompts and responses are confidential tenant data with defined retention. Conversation history is not automatically durable memory.
- **Confidence handling:** Prefer evidence coverage and conflict flags over a decorative global score. Clearly say when the available evidence cannot answer.
- **Human review:** Answers are advisory. Converting any suggestion into a task, communication or external write enters the Workflow Engine and its approval rules.
- **Failure behaviour:** Retrieval failure, context overflow, policy rejection or model timeout yields a bounded error/partial evidence view, never an uncited guess.
- **Observability:** Citation precision/coverage, unsupported-claim rate, answer usefulness, latency, token/cost, refusals, corrections and retrieval misses.
- **Beta scope:** Account-context questions and meeting preparation using authorised RevenueOS evidence.
- **Future scope:** Cross-relationship planning and product-specific reasoning after dedicated evaluations; no general autonomous agent is assumed.

## 5. Integration Layer

- **Responsibilities:** Provide replaceable adapters for transcription, structured generation, embeddings, object storage and future calendars, mail, meeting platforms and CRMs.
- **Inputs:** Minimal provider-specific commands created by domain services after authorisation and policy checks.
- **Outputs:** Normalised data, capability/health state and typed execution receipts or error classifications.
- **Storage boundaries:** Provider tokens and secrets are isolated; external IDs, cursors and required snapshots are tenant-scoped; connected systems remain authoritative.
- **Confidence handling:** Provider confidence is retained with its origin and mapped carefully; absence of a provider score is not converted to false precision.
- **Human review:** Integration adapters cannot create approval. They execute only a valid, capability-scoped domain command.
- **Failure behaviour:** Typed authentication, rate-limit, conflict, validation, transient and unknown-outcome errors; circuit breaking or backoff remains bounded.
- **Observability:** Provider latency, quota/rate-limit state, webhook lag, token refresh health, retries, reconciliation and deletion status with secrets/content redacted.
- **Pilot/Beta scope:** Deterministic mocks for tests; real adapters introduced one by one only when end-to-end behaviour is validated.
- **Future scope:** Phone, JobAdder, Slack and customer success connectors through the same ports, not provider logic inside domain services.

## Structured outputs

- Every model-generated machine-consumed output uses a versioned Pydantic schema with unknown fields rejected.
- Identifiers, actions and permissions are assigned by application code, never accepted blindly from the model.
- Text spans/citations reference immutable source and transcript versions.
- Schema validation failure may trigger one bounded repair attempt; persistent failure becomes reviewable failure.
- Free-form model prose is not parsed with fragile regular expressions to trigger actions.

Candidate artefact envelope:

| Field | Meaning |
| --- | --- |
| `artifactType` / `schemaVersion` | Stable contract and migration path |
| `sourceIds` / `sourceSpans` | Authorised evidence behind claims |
| `claims` | Atomic, typed statements rather than one opaque blob |
| `confidence` | Component-specific evidence/model signal and explanation |
| `promptVersion` / `modelRef` | Reproducibility metadata without secrets |
| `status` | Generated, review-required, accepted, rejected, superseded or deleted |

## Prompt versioning and model abstraction

- Prompts are versioned, reviewed artefacts with owner, purpose, schema, test set, changelog and rollback reference.
- The domain depends on `TranscriptionProvider`, `StructuredAIProvider` and `EmbeddingProvider` ports, not OpenAI request types.
- A model configuration identifies capability class, provider model, parameters, timeout and cost ceiling.
- Production rollout uses offline evaluation, shadow or internal testing, then a scoped feature rollout. A model alias change is treated as a behavioural change.
- Deterministic mock adapters cover tests; mock success is never presented as a real external capability.

## Source attribution and confidence

- Every material factual claim must cite an authorised source span or be labelled as user-provided/unsupported.
- Citations preserve source version so later corrections can invalidate dependent claims.
- Confidence is used for routing: block, require review or allow a low-risk candidate. It is not shown as misleading decimal precision without calibration.
- UI language distinguishes confirmed external fact, user-confirmed memory, direct quotation, model inference, conflict and unknown.
- Source authority and recency are explicit inputs; a newer inference does not automatically outrank an authoritative CRM field.

## Hallucination safeguards

1. Delimit and label customer content as untrusted data, never instructions.
2. Retrieve only authorised sources and include a “not enough evidence” path.
3. Require structured output and validate identifiers against same-tenant records.
4. Reject uncited material claims from memory promotion or external proposals.
5. Give models no implicit tools, secrets, network access or write authority.
6. Bind approvals to deterministic application-rendered diffs/content versions.
7. Continuously evaluate unsupported claims, source mismatch and prompt-injection resistance.

## Evaluation framework

### Evaluation layers

- **Contract:** Schema validity, required citations, identifier validity and latency/cost ceiling.
- **Offline quality:** Curated synthetic and consented/redacted test cases for transcription, summary, commitments, matching, memory and account Q&A.
- **Safety:** Prompt injection, sensitive data, unsupported claims, cross-tenant retrieval and prohibited action generation.
- **Human review:** Factual correction, edit distance, acceptance/rejection reason and source usefulness.
- **Workflow outcome:** Time to review, follow-up completion, CRM proposal accuracy and repeated memory usefulness.

### Release gates

- Dataset version and rubric are recorded.
- High-severity safety and tenant tests have zero accepted failures.
- Citation coverage and unsupported-claim thresholds are met by artefact type.
- Cost and p95 latency remain within a documented envelope.
- A rollback model/prompt version is available.
- Human reviewers sample changed behaviour before broader rollout.

Customer content is not silently added to evaluation datasets. Any use requires lawful authority, documented minimisation and a separate explicit choice where required.

## Redaction and sensitive data handling

- Apply deterministic redaction before model calls where workflow value does not require the sensitive value.
- Preserve a reversible mapping only when the user workflow requires reconstruction, encrypted and tenant-scoped.
- Classify and restrict sensitive categories; do not infer protected attributes or employment/health/legal conclusions for beta workflows.
- Minimise provider payload and retention; use provider settings that prohibit training on customer content where available.
- Never log transcripts, prompts, outputs, tokens, email bodies or recording URLs.
- Exclusion/deletion immediately prevents future retrieval and model context inclusion.

## Correction loops

1. User corrects transcript, match, artefact or memory.
2. System versions the corrected item and identifies dependent artefacts.
3. Invalidated outputs stop serving immediately.
4. Bounded regeneration occurs only where useful; consequential approvals are invalidated if content changed.
5. Correction metadata contributes to aggregate quality analysis without exposing raw content.

The product should learn through evaluated product changes, not uncontrolled per-tenant prompt mutation.

## Auditability

Record metadata for source receipt, consent evidence, job/model/prompt/schema versions, source citations, review decisions, corrections, approvals, execution attempts, provider receipts, access-sensitive administration and deletion. Audit records should be append-only in intent, tenant-scoped and content-minimised.

## Cost controls

- Set maximum file duration/size, transcript/context length, output tokens and retry counts.
- Cache immutable reviewed artefacts and reuse source processing by idempotency key.
- Use the lowest-capability model that passes the evaluation gate for each task.
- Batch embeddings or low-priority work within latency objectives without delaying user-visible review.
- Track cost per organisation, meeting and completed workflow; set alerts and hard policy ceilings.
- Summarise old context into source-backed memory rather than repeatedly sending full history.

## Latency expectations

| Interaction | Target experience |
| --- | --- |
| Search/navigation retrieval | p95 under 2 seconds |
| Account question | first useful state under 3 seconds; completed answer p95 under 12 seconds |
| Meeting brief | cached/open under 2 seconds; new brief p95 under 20 seconds |
| Follow-up or CRM proposal draft | p95 under 15 seconds after reviewed evidence |
| Transcript/meeting analysis | asynchronous; stage progress visible within 5 seconds and no request held open |

Targets are hypotheses until real workload tests establish provider and file-size envelopes. Accuracy and safe failure outrank artificial streaming.

## Unresolved technical decisions

- Which transcription model/provider meets accuracy, residency, cost and retention requirements for the pilot?
- Whether embeddings are needed for the first memory retrieval implementation or deterministic structured retrieval is sufficient.
- Which confidence signals can be calibrated well enough to expose to users.
- Which data may be retained for evaluation and under what explicit customer agreement.
- Model/provider regional availability for the first launch geography.

## Related documents

- [Core workflows](../02-design/core-workflows.md)
- [Target domain model](../03-engineering/target-domain-model.md)
- [Privacy, security and trust model](../03-engineering/privacy-security-and-trust-model.md)
- [Integration strategy](../05-integrations/integration-strategy.md)
- [Product roadmap to beta](../06-roadmap/product-roadmap-to-beta.md)
