# Meeting Risks & Blockers intelligence

## Product behaviour

WO-004C4 adds the fourth Meeting Intelligence capability. An authorised user
can request **Risks & Blockers** from the current usable meeting transcript.
The API queues work; the durable worker invokes the configured deterministic
mock or OpenAI provider; and the Intelligence panel polls every three seconds
until a safe terminal state is reached.

This capability extracts only transcript-supported obstacles, dependencies,
objections, uncertainty or exposure that could prevent or delay progress. It
does not create mitigation plans, tasks, probabilities, questions, CRM fields
or deal scores. Executive Summary, Decisions, Action Items and Risks & Blockers
have independent jobs, idempotency and append-only artefacts.

## End-to-end flow

1. `POST /api/v1/meetings/{meetingId}/intelligence/risks-blockers`
   authenticates the user, derives the active organisation and locks the
   same-tenant meeting.
2. The service requires the current non-empty transcript, bounded to 50,000
   trimmed characters. It returns an equivalent pending, running or completed
   job when one exists.
3. New work pins transcript ID/version and stores job type `risks_blockers`,
   prompt `risks_blockers` v1 and schema v1.
4. The worker restores transaction-local tenant context and loads exactly the
   pinned meeting/transcript version.
5. `RisksBlockersExecutor` resolves the prompt and registry-derived schema,
   renders JSON-delimited minimum source values and invokes the configured
   provider outside a database transaction.
6. Malformed or schema-invalid output retries within the bounded structured
   output limit. Pydantic remains authoritative.
7. The completion transaction rechecks ownership and cancellation, persists a
   versioned validated artefact, then completes the job.
8. `GET /api/v1/meetings/{meetingId}/intelligence/risks-blockers` returns only
   product-safe lifecycle state and the latest completed result for the current
   transcript.

Historical transcript bodies are not retained. A transcript update permits a
new job while the old artefact remains append-only.

## Schema v1

`RisksBlockersArtifactContent` in
`apps/api/src/revenueos/ai_contracts.py` is the authoritative frozen schema:

```json
{
  "risks": [
    {
      "risk": "Procurement approval may delay implementation.",
      "category": "procurement",
      "severity": "high",
      "owner": "Customer Procurement",
      "confidence": 0.93,
      "evidence": "The customer said procurement usually takes six weeks."
    }
  ]
}
```

`risks` is required, may be empty and contains at most 25 items. Unknown fields
are rejected at every level.

| Field | Contract |
| --- | --- |
| `risk` | Trimmed concise plain text, 5–500 characters, describing a genuine obstacle, dependency, objection, uncertainty, exposure or delaying condition. |
| `category` | Exactly `budget`, `procurement`, `legal`, `security`, `technical`, `integration`, `timeline`, `implementation`, `stakeholder`, `competitor`, `commercial`, `resourcing`, `dependency` or `other`. |
| `severity` | Exactly `high`, `medium` or `low`, supported by transcript evidence. High is a likely block, material delay or serious threat; medium is meaningful but not decisive; low is a limited concern or early warning. |
| `owner` | Required nullable field. A present owner is trimmed plain text of 1–200 characters and is used only when the responsible person, team or organisation is clear. |
| `confidence` | Finite number from 0 through 1 inclusive. |
| `evidence` | Required brief paraphrased plain text, 5–500 characters, supporting the risk without a long quotation or unnecessary sensitive detail. |

Probability, mitigation, action item, due date, open question, decision,
follow-up email, CRM and deal-score fields are prohibited.

## Extraction rules

A decision such as “The pilot was approved” is not a risk. An action such as
“Kevin will send the agreement” is not a risk. “Has legal approved the
contract?” is an open question and is not a risk unless the transcript also
establishes a threatening consequence. “Legal review may delay contract
signature” is a risk.

The prompt and deterministic mock recognise transcript-grounded examples such
as unapproved budget, procurement delay, outstanding legal or security review,
technical or integration uncertainty, competitor pressure, a missing decision
maker, insufficient resources, implementation dependencies, timeline
constraints, commercial objections and stakeholder resistance. Neutral facts,
completed problems, general discussion, vague negativity and questions without
a consequence are excluded.

A successful result may be `{"risks": []}`. The UI displays **No risks or
blockers were identified in this meeting.** and does not treat it as an error.

## Prompt and providers

Prompt key/version `risks_blockers`/`1` references schema
`risks_blockers`/`1`. The only variables are JSON-encoded `meeting_title`,
`meeting_date` and `transcript_text`. The prompt requires supported extraction,
normalised categories and qualitative severity, nullable supported ownership,
finite confidence and brief paraphrased evidence. It explicitly distinguishes
Decisions, Action Items and Open Questions, excludes probability and mitigation,
treats transcript/title as untrusted data and ignores embedded prompt injection.
Rendered prompt content is neither logged nor persisted.

`DeterministicMockAIProvider` remains the zero-network local/test default. Its
narrow rules return stable valid risks, multiple or empty results, nullable
owners, normalised procurement/budget/competitor fixtures and deterministic
malformed/schema-invalid sequences. It is labelled non-production intelligence.

`OpenAIProvider` explicitly allows matching `risks_blockers` input and uses the
existing asynchronous Responses API strict JSON Schema path with `store=false`
and SDK retries disabled. Infrastructure tests, mismatched and unsupported job
types are rejected before SDK invocation. Tests inject fakes and never call the
real OpenAI API.

> `AI_PROVIDER=openai` sends Risks & Blockers instructions and the selected
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

Telemetry and audit metadata may include risk count, empty-result flag and
counts by severity/category. Risk text, owner text, evidence, transcript,
rendered prompt and raw provider output are prohibited from logs and audits.
Audits reuse `intelligence_requested`, `ai_job_created`,
`ai_job_status_changed` and `ai_artifact_created`.

## API, UI and polling

POST returns safe job ID, queued/running/completed status, created flag,
transcript version and timestamps. New work returns `202`; an existing
equivalent returns `200`. GET supports `empty`, `queued`, `running`,
`completed`, `failed` and `cancelled`. Worker IDs, leases, raw errors, prompts,
transcripts, provider responses and provider configuration are never exposed.

The accessible Risks & Blockers panel appears after Action Items. It provides
unavailable, empty/generate, queued, processing, completed, successful-empty,
failed/retry and cancelled states. Completed cards show human-readable category
and severity, optional owner, confidence percentage, brief evidence and
generated time. It has no probability or mitigation display/editor.

The panel owns one non-overlapping `setTimeout` polling chain at three-second
intervals. Polling stops at completed, failed or cancelled, clears on unmount
and aborts an in-flight request when the panel is removed. No WebSocket was
added.

## Migration, security, tests and limitations

Migration `0010_risks_blockers` widens only the existing AI job and artefact
type checks. It adds no table, column or RLS policy and restores the SQLite
trace/immutability triggers after batch alteration. Downgrade deletes Risks &
Blockers artefacts/jobs before restoring the Action Items-era checks. Forced
PostgreSQL RLS, composite tenant keys and explicit repository organisation
predicates remain unchanged.

Coverage includes schema boundaries and immutability; prompt variables and
injection handling; deterministic populated/empty/nullable/malformed cases;
OpenAI strict schema and unsupported pre-SDK rejection; executor retry and safe
failure; API state, idempotency, append-only persistence, transcript changes and
tenant denial; migration/drift and RLS suites; accessible UI lifecycle and
deterministic polling; and a mock-only Playwright generate/complete/refresh flow.

Known limitations: extraction is limited to transcript evidence; owner may be
null; severity is qualitative, not probabilistic; there is no mitigation
planning or risk editing; prompts/schemas remain code-deployed; the mock is
deliberately narrow; OpenAI sends content externally when selected; cost uses
the current integer project convention; historical transcript bodies are not
retained; and production customer data remains prohibited.
