# Meeting Decisions intelligence

## Product behaviour

WO-004C2 adds RevenueOS's second Meeting Intelligence capability. An authorised
user opens a meeting's **Intelligence** tab and requests **Decisions** from the
current usable transcript. The API queues work; it never calls a provider
synchronously. The separately running worker validates and persists a versioned
artefact, while the browser polls safe product state every three seconds.

Decisions is independent from Executive Summary and the later WO-004C3 Action
Items capability. Each capability has its own job and artefact for the same
transcript version. WO-004C2 itself did not add Action Items, due dates, Risks,
Open Questions, follow-up content, CRM suggestions, recording, transcription
or automation.

## End-to-end flow

1. `POST /api/v1/meetings/{meetingId}/intelligence/decisions` authenticates the
   user, derives the active organisation and locks the same-tenant meeting.
2. The service requires the meeting's current non-empty transcript, bounded to
   50,000 trimmed characters, and returns an equivalent pending, running or
   completed Decisions job when one exists.
3. Otherwise it pins the transcript ID/version and creates a pending
   `decisions` job with prompt `decisions` v1 and schema `decisions` v1.
4. The durable worker claims the job, restores tenant context and loads only
   the exact pinned meeting/transcript trace.
5. `DecisionsExecutor` resolves the immutable prompt and registry-derived
   schema, JSON-delimits the minimum source fields and invokes the configured
   mock or OpenAI provider outside a database transaction.
6. The common parser validates a complete JSON object. Malformed or
   schema-invalid output retries within the configured structured-output bound.
7. The completion transaction rechecks ownership and cancellation, creates an
   append-only `decisions` artefact and only then completes the job.
8. `GET /api/v1/meetings/{meetingId}/intelligence/decisions` returns the safe
   lifecycle state and latest completed artefact for the current transcript.

Historical transcript bodies are not retained. If the transcript advances,
the previous artefact remains append-only but the current UI becomes empty and
a new transcript-version-bound job may be requested.

## Decisions schema v1

The authoritative model is `DecisionsArtifactContent` in
`apps/api/src/revenueos/ai_contracts.py`. It is frozen, rejects unknown fields
and serialises as:

```json
{
  "decisions": [
    {
      "decision": "Proceed with the proposed pilot in September.",
      "owner": "Jane Smith",
      "status": "confirmed",
      "confidence": 0.94,
      "evidence": "The transcript records agreement to begin the pilot in September."
    }
  ]
}
```

`decisions` is required, may be empty, and contains at most 25 items. Every item
has exactly these fields:

| Field | Contract |
| --- | --- |
| `decision` | Trimmed plain text, 5–500 characters; an actual agreement, approval, rejection, deferral or commitment rather than a topic, question, suggestion or task. |
| `owner` | Required nullable field; when present it is trimmed plain text of 1–200 characters and must be supported by the transcript. |
| `status` | Exactly `confirmed`, `tentative`, `rejected` or `deferred`. |
| `confidence` | Finite number from 0 through 1 inclusive. |
| `evidence` | Required brief paraphrased plain text, 5–500 characters, grounded in the transcript without a long quotation or unnecessary sensitive detail. |

The schema contains no due date, priority, task, risk, open question, email or
CRM field. Pydantic validation is authoritative after any provider-level strict
JSON Schema response.

## Decisions versus Action Items

A decision records what participants resolved or committed to: for example,
approval to start a pilot, rejection of a commercial option or a deliberate
deferral. An Action Item records work somebody must perform. “Proceed with the
September pilot” may be a decision; “Jane must draft the pilot plan by Friday”
is an Action Item and is excluded even when it follows from that decision.

Discussion, proposals and questions are not promoted to decisions. When the
transcript supports none, the successful output is `{"decisions": []}` and the
UI says **No decisions were identified in this meeting.** This is not a
failure.

## Prompt v1 and untrusted input

The code-deployed prompt key/version is `decisions`/`1`; it references schema
`decisions`/`1`. It instructs the provider to:

- extract only transcript-supported decisions;
- separate decisions from topics, proposals, questions and Action Items;
- return an empty list when appropriate;
- avoid invented owners or commitments;
- normalise status and provide confidence plus brief paraphrased evidence;
- treat title/transcript content as untrusted data and ignore embedded
  prompt-injection attempts; and
- return only the strict structured object without later-capability fields.

The only variables are JSON-encoded `meeting_title`, `meeting_date` and
`transcript_text`. Missing or unknown variables fail before provider
invocation. Rendered prompts and transcript content are never logged or
persisted as prompt trace.

## Providers

`DeterministicMockAIProvider` remains the default. It performs no network call,
needs no API key and produces stable schema-valid Decisions output from simple
explicit decision markers. It supports one-or-more decisions, a valid empty
list, malformed JSON and schema-invalid deterministic test sequences. Its
keyword extraction is visibly mock behaviour, not an intelligence-quality
claim.

`OpenAIProvider` explicitly allows `executive_summary`, `decisions` and the
later `action_items` capability with their matching typed inputs.
`infrastructure_test` and unknown job types are rejected before the SDK call.
The adapter uses the existing asynchronous
Responses API, `store=false`, disabled SDK retries and the registry-derived
strict JSON Schema. Refusal, incomplete output and provider failures retain the
existing safe classification. Automated tests inject SDK-shaped fakes; no test
calls OpenAI.

> Setting `AI_PROVIDER=openai` sends the rendered Decisions instructions and
> selected transcript to OpenAI. Production customer data remains prohibited
> until identity, consent, retention/export/erasure, provider privacy and
> operational controls are approved.

## Idempotency and append-only persistence

Equivalent active/completed work is identified by organisation, meeting,
transcript version, job type, prompt version and schema version. The meeting row
lock serialises capability requests and the existing organisation-scoped unique
idempotency key resolves a concurrent race. Failed or cancelled work receives a
new bounded retry ordinal; a transcript-version change permits new work.

Executive Summary uses a different job type/key and is therefore independent.
Completed artefacts are never updated. Logical Decisions artefact versions are
scoped by organisation, meeting, transcript ID/version and artefact type.

Migration `0008_decisions` is essential because the existing database check
constraints allowed only infrastructure test and Executive Summary. It widens
only job/artefact type checks, adds no table or column and restores the existing
SQLite trace/immutability triggers after batch alteration. PostgreSQL forced
RLS and composite tenant keys are unchanged. Downgrade deletes Decisions rows
before restoring the earlier type checks.

## API and UI states

The POST response contains only job ID, normalised queued/running/completed
status, whether it was created, transcript version and safe lifecycle
timestamps. A new job returns `202`; an existing equivalent job returns `200`.

The GET response supports `empty`, `queued`, `running`, `completed`, `failed`
and `cancelled`, plus generation availability, a product-safe reason/message,
safe timestamps and completed Decisions content. It never returns worker IDs,
leases, prompts, transcripts, raw errors, provider responses or configuration.

The Decisions panel appears beneath Executive Summary and provides transcript
unavailability, empty/generate, queued, processing, completed, successful-empty,
failed/retry and cancelled states. Completed cards show decision, optional
owner, human-readable status, confidence percentage, evidence and generation
time. Controls are semantic, keyboard accessible and submission-disabled while
active.

Polling uses one non-overlapping request chain per mounted panel and a
three-second `setTimeout`. It stops on completed, failed or cancelled, aborts
the current request and clears its timer on unmount, and therefore stops when
the Intelligence tab is no longer active. No WebSocket was added.

## Traceability, security and telemetry

The existing job and artefact fields retain organisation, meeting, transcript
version, job, prompt/schema versions, provider/model/request ID, structured
output attempts, tokens, integer cost/currency, finish status, processing
duration and creation time where supported. Only normalised validated Decisions
content reaches `content_json`; prompt, transcript, raw/invalid provider output,
SDK objects and secrets do not.

All repositories use explicit organisation predicates and transaction-local
trusted tenant context. Composite foreign keys and forced RLS continue to block
cross-tenant meeting, transcript, job and artefact attachment. The API derives
organisation only from verified auth context and returns cross-tenant IDs as
not found.

Content-free logs cover request/idempotent return, execution start, transcript
character count/version, prompt/schema resolution, validation, decision count,
empty-result flag, artefact creation, completion and bounded failure code. The
existing audit actions remain `intelligence_requested`, `ai_job_created`,
`ai_job_status_changed` and `ai_artifact_created`. Decision text, owner,
evidence, transcripts, prompts and raw output are excluded from telemetry and
audit metadata.

## Testing and known limitations

Backend tests cover schema bounds/immutability, prompt variables and injection
separation, mock one/none/malformed output, OpenAI strict schema/allowlist and
safe failures, executor retry/exhaustion, API lifecycle/idempotency/isolation,
append-only trace and migration rollback. UI tests use deterministic timers for
rendering, duplicate prevention, polling termination/cleanup, empty results and
retry. Playwright exercises a mock-only generate, queued, completed and refresh
journey.

Decisions quality is limited to transcript evidence. Owners may be null. The
mock is deterministic rather than intelligent. Prompts/schemas remain
code-deployed. There is no Action Item or due-date extraction, immutable
historical transcript body, accurate cost calculation, provider/model UI,
recording, transcription, external integration or production customer-data
approval.
