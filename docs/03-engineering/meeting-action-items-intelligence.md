# Meeting Action Items intelligence

## Product behaviour

WO-004C3 adds RevenueOS's third Meeting Intelligence capability. An authorised
user opens a meeting's **Intelligence** tab and requests **Action Items** from
the current usable transcript. The API queues work without calling a provider
synchronously. The durable worker validates and persists a versioned artefact,
while the mounted browser panel polls safe product state every three seconds.

Action Items, Decisions and Executive Summary have independent jobs,
idempotency and artefacts. Action Items records only concrete work that a
person or group committed or agreed to perform. It does not turn a decision,
topic, risk, question, aspiration or vague suggestion into work, and it does
not create or edit a RevenueOS task.

## End-to-end flow

1. `POST /api/v1/meetings/{meetingId}/intelligence/action-items` authenticates
   the user, derives the organisation and locks the same-tenant meeting.
2. The service requires the current non-empty transcript, bounded to 50,000
   trimmed characters, and returns an equivalent pending, running or completed
   Action Items job when one exists.
3. Otherwise it pins transcript ID/version and creates an `action_items` job
   with prompt `action_items` v1 and schema `action_items` v1.
4. The worker restores trusted tenant context and loads only that exact
   meeting/transcript trace, including the stored meeting date.
5. `ActionItemsExecutor` resolves the versioned prompt and registry-derived
   schema, safely renders JSON-delimited source values and invokes the selected
   mock or OpenAI provider outside a database transaction.
6. The shared parser accepts only a complete schema-valid object. Malformed or
   invalid output retries within the configured structured-output bound.
7. The completion transaction rechecks ownership and cancellation, writes an
   append-only `action_items` artefact and completes the job only after the
   artefact is persisted.
8. `GET /api/v1/meetings/{meetingId}/intelligence/action-items` returns the
   product-safe lifecycle state and latest completed artefact for the current
   transcript.

Historical transcript bodies are not retained. When the transcript version
changes, the prior artefact remains append-only but the current panel returns
to empty and may queue new work.

## Action Items schema v1

`ActionItemsArtifactContent` in
`apps/api/src/revenueos/ai_contracts.py` is authoritative. It is frozen,
rejects unknown fields and serialises as:

```json
{
  "action_items": [
    {
      "task": "Send the revised commercial proposal.",
      "owner": "Kevin",
      "due_date": "2026-08-01",
      "priority": "high",
      "status": "open",
      "confidence": 0.94,
      "evidence": "Kevin committed to send the revised proposal by 2026-08-01."
    }
  ]
}
```

`action_items` is required, may be empty and contains at most 25 items. Every
item has exactly these fields:

| Field | Contract |
| --- | --- |
| `task` | Trimmed plain text, 5–500 characters, describing a concrete next step, deliverable, commitment or follow-up rather than a decision, risk, question or suggestion. |
| `owner` | Required nullable field. A present owner is trimmed plain text of 1–200 characters and is included only when the transcript supports the assignment. Discussion alone does not establish ownership. |
| `due_date` | Required nullable field. A present value is a real calendar date in exact `YYYY-MM-DD` form. Urgency alone never creates a date. |
| `priority` | Exactly `high`, `medium` or `low`, grounded by the transcript. `high` requires explicit urgency, a blocking dependency or time-critical commitment; `low` requires clear non-urgency. A normal committed follow-up defaults to `medium`. |
| `status` | Exactly `open`. Completion, cancellation and manual status editing are not part of this capability. |
| `confidence` | Finite number from 0 through 1 inclusive. |
| `evidence` | Required brief paraphrased plain text, 5–500 characters, supporting the task and any owner/due date without a long quotation or unnecessary sensitive detail. |

Pydantic validation remains authoritative after provider-level strict JSON
Schema. No task-system ID, reminder, completion timestamp, email, CRM, risk,
blocker, open-question or decision-status field is allowed.

## Action Items versus Decisions

“The pilot was approved” is a Decision and is not an Action Item. “Kevin will
send the pilot agreement” is an Action Item. The prompt and deterministic mock
exclude statements such as “We should consider changing pricing”, “Maybe Jane
can review it”, “It would be good to follow up”, “Can someone send the
document?” and “Pricing remains a concern”.

When the transcript contains no real commitment, the successful output is
`{"action_items": []}` and the UI says **No action items were identified in
this meeting.** That state is not a failure.

## Conservative relative-date normalisation

`normalise_action_item_due_date` in
`apps/api/src/revenueos/ai_action_items_dates.py` implements the deliberately
narrow deterministic calendar used by the mock and documented for providers:

- the calendar date is taken directly from the stored meeting date; the
  current system date is never consulted and no timezone conversion is applied
  during interpretation;
- `today` is the meeting date and `tomorrow` is the following date;
- `this <weekday>` means that weekday in the same ISO Monday-starting week and
  returns null if it has already passed;
- `next <weekday>` means that weekday in the following ISO week;
- `end of this week` means Friday of the same business week and returns null if
  Friday has passed;
- `end of next week` means Friday of the following business week; and
- an exact valid `YYYY-MM-DD` remains unchanged.

Optional leading “by” is ignored. `soon`, `later`, `next time`, `in a few
days`, `sometime next month`, `before launch`, `ASAP`, impossible dates and
other unsupported or ambiguous phrases return null. Urgency may affect
priority but never a due date. The OpenAI prompt instructs the model to apply
the same narrow vocabulary; the output schema then rejects invalid calendar
dates. The application does not run a broad natural-language date library.

## Prompt and providers

The code-deployed prompt key/version is `action_items`/`1`, referencing schema
`action_items`/`1`. Its only variables are JSON-encoded `meeting_title`,
`meeting_date` and `transcript_text`. It requires concrete commitments, empty
success when none exist, supported owners/dates/priorities, `open` status,
finite confidence and brief paraphrased evidence. It explicitly separates
actions from Decisions and later capabilities, treats transcript/title as
untrusted data and ignores embedded prompt-injection attempts. Missing or
unknown variables fail before provider invocation. Rendered prompts are never
logged or persisted.

`DeterministicMockAIProvider` remains the default. It requires no key, makes no
network call and produces stable schema-valid output for explicit commitments,
multiple or no actions, nullable owner/date, supported relative dates and
decision-only transcripts. Deterministic malformed and schema-invalid
sequences test retry/failure behaviour. Its narrow pattern matching is
development/test behaviour, not production intelligence.

`OpenAIProvider` explicitly allows matching Executive Summary, Decisions and
Action Items inputs. `infrastructure_test`, mismatched and unknown job types
are rejected before SDK invocation. The adapter uses the asynchronous
Responses API, `store=false`, disabled SDK retries and registry-derived strict
JSON Schema. Refusal, incomplete output and provider errors retain their safe
existing handling. Tests use injected SDK-shaped fakes and never call OpenAI.

> `AI_PROVIDER=openai` sends Action Items instructions and the selected
> transcript to OpenAI. Production customer data remains prohibited until
> production identity, consent, retention/export/erasure, provider privacy and
> operational controls are approved.

## Idempotency, persistence and traceability

Equivalent work is scoped by organisation, meeting, transcript version, job
type, prompt version and schema version. A meeting-row lock serialises normal
requests and the tenant-scoped unique idempotency key closes concurrent races.
Pending, running and completed equivalents are reused. Failed or cancelled
work receives a new bounded retry ordinal. A transcript-version change or a
different capability may create a separate job.

Completed artefacts are append-only and versioned by organisation, meeting,
transcript ID/version and artefact type. Existing job/artefact trace records
organisation, meeting, transcript version, job, prompt/schema versions,
provider/model/request ID, structured-output attempts, tokens, integer
cost/currency, finish status, duration and creation time where supported. Only
normalised validated Action Items content is persisted. Prompt, transcript,
raw or invalid provider output, SDK objects, keys and secrets are not.

Migration `0009_action_items` is required because existing job/artefact type
checks stopped at Decisions. It widens only those two checks, adds no table,
column or policy and restores SQLite trace/immutability triggers after batch
alteration. Forced PostgreSQL RLS and composite tenant keys are unchanged. A
downgrade deletes Action Items artefacts/jobs before restoring Decisions-era
checks.

## API, UI, polling and telemetry

POST returns only job ID, queued/running/completed status, whether the row was
created, transcript version and safe timestamps. New work returns `202`; an
existing equivalent returns `200`. GET supports `empty`, `queued`, `running`,
`completed`, `failed` and `cancelled`, with generation availability, safe
messages/timestamps and completed content. It never exposes worker identity,
leases, prompts, transcripts, raw errors/responses or provider configuration.

The Action Items panel follows Executive Summary and Decisions in the existing
Intelligence tab. It provides transcript-unavailable, empty/generate, queued,
processing, completed, successful-empty, failed/retry and cancelled states.
Completed cards show task, optional owner/date, human-readable priority,
`Open` status, confidence percentage, evidence and generated time. There are
no completion checkboxes, editors, reminders or integration controls.

Each mounted capability owns one non-overlapping `setTimeout` polling chain at
three-second intervals. Polling stops on completed, failed or cancelled,
clears its timer and aborts an in-flight request on unmount, including when the
Intelligence panel is removed. No WebSocket was added.

Content-free telemetry covers request/idempotent return, execution start,
transcript version/character count, prompt/schema resolution, validation,
action count, empty result, owner count, due-date count, artefact creation,
completion and bounded failure code. Audits reuse
`intelligence_requested`, `ai_job_created`, `ai_job_status_changed` and
`ai_artifact_created`. Task, owner, due-date source language, evidence,
transcript, prompt and raw output never enter logs or audit metadata.

## Security, testing and known limitations

Trusted authentication derives the active organisation. Repositories retain
explicit organisation predicates; transaction-local tenant context, composite
foreign keys and forced RLS prevent cross-tenant meeting, transcript, job and
artefact access or attachment. OpenAI receives customer content only when the
server operator explicitly selects it.

Tests cover schema bounds/immutability, nullable fields, impossible dates,
prompt variables/injection separation, deterministic date rules, mock
one/many/none/malformed output, OpenAI strict schema/allowlist, executor retry
and cancellation boundaries, API lifecycle/idempotency/isolation, append-only
persistence, migration rollback/re-upgrade, RLS, UI polling/cleanup and a
mock-only Playwright generate/refresh journey.

Extraction remains limited to transcript evidence. Owner and due date may be
null; ambiguous dates remain null. The mock is deterministic rather than
intelligent. Prompts and schemas are code-deployed. Historical transcript
bodies are not retained. Cost remains the current integer-minor-unit project
convention. There is no completion tracking, task editing/creation, reminder,
calendar/email/CRM integration, recording, transcription or production
customer-data approval.
## Unified workspace navigation

WO-005 presents this capability in the unified Meeting Intelligence workspace
and aggregate read. Its individual API, strict schema, durable job/artefact,
retry and transcript-grounding rules are unchanged. See
[Unified Meeting Intelligence](unified-meeting-intelligence.md).
