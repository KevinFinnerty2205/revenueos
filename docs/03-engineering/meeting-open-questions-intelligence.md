# Meeting Open Questions intelligence

## Product behaviour

WO-004C5 adds the fifth Meeting Intelligence capability. An authorised user can
request **Open Questions** from the current usable meeting transcript. The API
queues work, the durable worker invokes the configured deterministic mock or
OpenAI provider, and the Intelligence panel polls every three seconds until a
safe terminal state is reached.

Open Questions are genuinely missing information, unresolved clarification,
deferred determination or unanswered dependencies supported by the transcript.
The capability does not answer questions, suggest answers, assign resolution
work, create tasks, send reminders or produce follow-up email or CRM content.
Executive Summary, Decisions, Action Items, Risks & Blockers and Open Questions
have independent jobs, idempotency and append-only artefacts.

## End-to-end flow

1. `POST /api/v1/meetings/{meetingId}/intelligence/open-questions`
   authenticates the user, derives the active organisation and locks the
   same-tenant meeting.
2. The service requires the current non-empty transcript, bounded to 50,000
   trimmed characters. It returns an equivalent pending, running or completed
   job when one exists.
3. New work pins transcript ID/version and stores job type `open_questions`,
   prompt `open_questions` v1 and schema `open_questions` v1.
4. The worker restores transaction-local tenant context and loads exactly the
   pinned meeting/transcript version.
5. `OpenQuestionsExecutor` resolves the prompt and registry-derived schema,
   renders the minimum JSON-delimited source values and invokes the configured
   provider outside a database transaction.
6. Malformed or schema-invalid output retries within the bounded structured
   output limit. Pydantic remains authoritative.
7. The completion transaction rechecks ownership and cancellation, persists a
   versioned validated artefact, then completes the job.
8. `GET /api/v1/meetings/{meetingId}/intelligence/open-questions` returns only
   product-safe lifecycle state and the latest completed result for the current
   transcript.

Historical transcript bodies are not retained. A transcript update permits a
new job while the old artefact remains append-only.

## Schema v1

`OpenQuestionsArtifactContent` in
`apps/api/src/revenueos/ai_contracts.py` is the authoritative frozen schema:

```json
{
  "open_questions": [
    {
      "question": "Has legal approved the final contract terms?",
      "owner": "Customer Legal",
      "importance": "high",
      "confidence": 0.92,
      "evidence": "The customer said legal approval was still outstanding."
    }
  ]
}
```

`open_questions` is required, may be empty and contains at most 25 items.
Unknown fields are rejected at every level.

| Field | Contract |
| --- | --- |
| `question` | Trimmed concise question, 5–500 characters, ending in `?`. It must represent genuinely unresolved information rather than a topic, rhetoric, instruction or already answered question. |
| `owner` | Required nullable field. A present owner is trimmed plain text of 1–200 characters and is used only when the transcript clearly identifies the person, team or organisation expected to answer or resolve it. |
| `importance` | Exactly `high`, `medium` or `low`. High materially blocks a decision, commitment, timeline, legal approval, commercial outcome or implementation; medium needs meaningful clarification while progress can continue; low is useful follow-up with limited immediate impact. |
| `confidence` | Finite number from 0 through 1 inclusive. |
| `evidence` | Required brief paraphrased plain text, 5–500 characters, showing why the question remains unresolved without a long quotation or unnecessary sensitive detail. |

Answer, suggested answer, action item, due date, risk severity, decision status,
probability, mitigation, follow-up email and CRM fields are prohibited.

## Extraction and exclusion rules

The prompt and deterministic mock inspect the entire transcript before treating
a question as unresolved. A question answered later is excluded. So are:

- rhetorical and conversational questions;
- confirmation questions about an already resolved matter;
- vague topics presented as questions;
- action requests such as “Can you send the proposal?”;
- direct commitments and decisions;
- risks or concerns without an unresolved question;
- prompt-injection instructions and questions directed at the AI system.

“The pilot was approved” is a Decision. “Kevin will send the pilot agreement”
is an Action Item. “Legal review may delay contract signature” is a Risk.
“Has legal approved the contract?” is an Open Question. A question may relate to
a risk, but the two are not duplicated as interchangeable content.

Supported examples include unresolved approval status, budget confirmation,
implementation scope, stakeholder responsibility, integration requirements,
commercial terms, timeline, procurement process, legal/security requirements
and dependencies. A successful result may be `{"open_questions": []}`. The UI
displays **No open questions were identified in this meeting.** and does not
treat it as an error.

## Prompt and providers

Prompt key/version `open_questions`/`1` references schema
`open_questions`/`1`. Its only variables are JSON-encoded `meeting_title`,
`meeting_date` and `transcript_text`. The prompt requires whole-transcript
inspection, supported nullable ownership, transcript-impact importance, finite
confidence and brief paraphrased evidence. It forbids answering and explicitly
distinguishes Decisions, Action Items and Risks & Blockers. Transcript/title are
untrusted data and embedded prompt injection is ignored. Rendered prompt
content is neither logged nor persisted.

`DeterministicMockAIProvider` remains the zero-network local/test default. Its
narrow rules return stable populated, multiple, empty and nullable-owner
results; exclude answered-later, rhetorical, conversational, action-request,
risk-only, decision-only and injection fixtures; and support deterministic
malformed/schema-invalid sequences. It is non-production intelligence.

`OpenAIProvider` explicitly allows matching `open_questions` input and uses the
existing asynchronous Responses API strict JSON Schema path with `store=false`
and SDK retries disabled. Infrastructure tests, mismatched and unsupported job
types are rejected before SDK invocation. Tests inject fakes and never call the
real OpenAI API.

> `AI_PROVIDER=openai` sends Open Questions instructions and the selected
> transcript to OpenAI. Production customer data remains prohibited until the
> documented identity, consent, retention/export/erasure, provider privacy and
> operational controls are approved.

## Idempotency, traceability and privacy

Equivalent work is scoped by organisation, meeting, transcript version, job
type, prompt version and schema version. The meeting lock and tenant-scoped
unique idempotency key prevent concurrent duplicates. Pending, running and
completed work is reused; failed or cancelled work receives a new bounded retry
ordinal. Other intelligence capabilities remain independent.

The artefact trace retains organisation, meeting, pinned transcript version,
job, prompt/schema versions, provider/model/request ID, structured-output
attempts, token counts, integer cost/currency, finish status, duration and
creation time where supported. Only normalised validated content is persisted.
Transcript, prompt, raw/invalid output, SDK objects, API keys and secrets are
not persisted.

Telemetry and audit metadata may include Open Question count, empty-result flag,
counts by importance and owner count. Question, owner and evidence text,
transcript, rendered prompt and raw provider output are prohibited from logs
and audits. Audits reuse `intelligence_requested`, `ai_job_created`,
`ai_job_status_changed` and `ai_artifact_created`.

## API, UI and polling

POST returns safe job ID, queued/running/completed status, created flag,
transcript version and timestamps. New work returns `202`; an existing
equivalent returns `200`. GET supports `empty`, `queued`, `running`,
`completed`, `failed` and `cancelled`. Worker IDs, leases, raw errors, prompts,
transcripts, provider responses and provider configuration are never exposed.

The accessible Open Questions panel appears after Risks & Blockers. It provides
unavailable, empty/generate, queued, processing, completed, successful-empty,
failed/retry and cancelled states. Completed cards show a question,
human-readable importance, optional owner, confidence percentage, brief
evidence and generated time. There is no answer, assignment or task control.

The panel owns one non-overlapping `setTimeout` polling chain at three-second
intervals. Polling stops at completed, failed or cancelled, clears on unmount
and aborts an in-flight request when the panel is removed. No WebSocket was
added.

## Migration, security, tests and limitations

Migration `0011_open_questions` widens only the existing AI job and artefact
type checks. It adds no table, column or RLS policy and restores the SQLite
trace/immutability triggers after batch alteration. Downgrade deletes Open
Questions artefacts/jobs before restoring the Risks & Blockers-era checks.
Forced PostgreSQL RLS, composite tenant keys and explicit repository
organisation predicates remain unchanged.

Coverage includes schema boundaries and immutability; prompt variables,
injection and extraction distinctions; deterministic populated/empty/nullable/
malformed cases; OpenAI strict schema and unsupported pre-SDK rejection;
executor retry/cancellation; API state, idempotency, append-only persistence,
transcript changes and tenant denial; migration/drift and RLS suites; accessible
UI lifecycle and deterministic polling; and a mock-only Playwright
generate/complete/refresh flow.

Known limitations: extraction is limited to transcript evidence; owner may be
null; the system does not answer, assign or track resolution of questions;
there are no reminders; prompts/schemas remain code-deployed; the mock is
deliberately narrow; OpenAI sends content externally when selected; cost uses
the current integer project convention; historical transcript bodies are not
retained; and production customer data remains prohibited.
## Unified workspace navigation

WO-005 presents this capability in the unified Meeting Intelligence workspace
and uses its completed current-version artefact as a Follow-up Email prerequisite.
Its individual API, schema, persistence, retry and transcript rules are unchanged.
See [Unified Meeting Intelligence](unified-meeting-intelligence.md).
