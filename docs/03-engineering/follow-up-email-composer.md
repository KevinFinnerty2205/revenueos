# Follow-up Email Composer

## Product behaviour

WO-004C6 adds the first customer-ready intelligence composer. An authorised
user can draft a concise Follow-up Email after Executive Summary, Decisions,
Action Items and Open Questions have completed for the same current transcript
version. The user selects `professional`, `friendly` or `executive`, observes
the durable queued/running state and can copy or regenerate the completed draft.

The composer drafts only. It does not send email, address recipients, create a
CRM activity, update a record, create a task or trigger an integration. Risks &
Blockers are deliberately excluded because they may contain internal concerns
that are unsuitable for customers.

## Hard source boundary and data flow

The Follow-up Email is composed only from four validated, persisted artefacts:

- Executive Summary `summary`;
- Decisions `decision` values, with a supported owner when present;
- Action Items `action`, owner and explicit due date when present; and
- Open Questions `question` values, with a supported owner when present.

The request service checks content-free transcript audit metadata to confirm
that these artefacts belong to the current transcript version and validates
their code-deployed prompt/schema versions. It then loads the four artefacts
through tenant-scoped AI repositories. The worker repeats those trace checks
and loads the same stable current-version source set.
Neither path queries the transcript body. `FollowUpEmailProviderInput` has no
transcript field, and prompt v1 has exactly five variables:
`executive_summary`, `decisions`, `action_items`, `open_questions` and `tone`.

```text
validated artefacts + requested tone
                │
                ▼
customer-safe source projection
                │
                ▼
follow_up_email prompt/schema v1
                │
                ▼
mock or OpenAI provider
                │
                ▼
strict schema + exact-fact grounding validation
                │
                ▼
append-only Follow-up Email artefact
```

Risks & Blockers, transcript text, meeting title/date, evidence fields,
confidence values from source items, internal notes and raw provider output do
not enter this composition flow. The post-provider grounding check requires the
returned summary, decision list, action-item list, open-question list and tone
to match the source projection exactly. Fabricated, removed or rewritten
meeting facts therefore fail before persistence, even if the JSON is otherwise
schema-valid.

## Schema v1

`FollowUpEmailArtifactContent` in
`apps/api/src/revenueos/ai_contracts.py` is the authoritative frozen schema:

```json
{
  "subject": "Following up on our discussion",
  "greeting": "Hello,",
  "summary": "We discussed the implementation plan and agreed the next steps.",
  "decisions": ["Proceed with the pilot — Owner: Customer team"],
  "action_items": ["Send the pilot plan — Owner: Kevin — Due: 2026-07-24"],
  "open_questions": ["Who will approve the production rollout?"],
  "closing": "Kind regards,",
  "tone": "professional",
  "confidence": 0.95
}
```

Every field is required and unknown fields are forbidden. Subject, greeting,
summary, closing and each list item are trimmed, bounded plain text. Each list
is capped at 25 items and may be empty. Tone is exactly `professional`,
`friendly` or `executive`; confidence is a finite number from 0 through 1.
HTML, markdown and send/integration fields are absent.

## Lifecycle, idempotency and regeneration

`POST /api/v1/meetings/{meetingId}/intelligence/follow-up-email` accepts only a
tone. It returns `202` for a new queued job and `200` for equivalent active or
completed work. Equivalence includes organisation, meeting, pinned source
transcript version, job type, prompt/schema versions and tone. Repeated clicks
while a matching job is pending or running reuse that job. Failed or cancelled
work may be retried.

A completed draft can be deliberately regenerated. Regeneration creates a new
append-only job/artefact even when the tone is unchanged, while prior artefacts
remain traceable. Selecting a different tone also creates distinct logical
work. If any required artefact is absent, invalid, from another transcript
version or no longer current, generation is unavailable and no job is queued.

The worker uses the established lease, retry, cancellation and atomic
completion path. Jobs persist the selected tone. Completed artefacts retain
organisation, meeting, transcript version, job, prompt/schema, provider/model/
request, structured-output attempts, token counts, integer cost/currency,
duration and timestamps under the existing trace contract.

## Prompt and providers

Prompt and output-schema key/version are `follow_up_email`/`1`. The prompt
requires exact copying of validated facts, a generic subject/greeting/closing,
the selected tone, natural omission of empty sections at presentation time and
no unsupported detail. It explicitly excludes risks, blockers, internal
concerns, competitor mentions, deal health, pricing concerns, internal notes,
evidence, transcript content and prompt-injection instructions embedded in the
source strings.

`DeterministicMockAIProvider` is the no-network default and returns a stable
schema-valid draft for all three tones. `OpenAIProvider` explicitly allowlists
the typed Follow-up Email operation and uses the existing Responses API strict
JSON Schema path with `store=false`, no tools, no streaming and SDK retries
disabled. Automated tests use fakes and never call the real OpenAI API.

When OpenAI is selected, only the customer-safe four-artefact projection and
tone are transmitted. The meeting transcript is never transmitted by the
Follow-up Email Composer. Other independently requested transcript-grounded
Meeting Intelligence capabilities retain their separately documented external
data flow.

## API, UI and copy behaviour

`GET /api/v1/meetings/{meetingId}/intelligence/follow-up-email` returns
`empty`, `queued`, `running`, `completed`, `failed` or `cancelled`, generation
availability, a product-safe unavailability reason or failure message, safe
timestamps, tone and completed schema content. It excludes source artefacts,
transcript, prompts, raw errors, leases, worker fields and provider payloads.

The unified Meeting Detail Intelligence workspace contains **Follow-up Email**
after Open Questions. The aggregate polling chain calls the safe idempotent
orchestration endpoint only after all four sources are ready. The section has
unavailable, not-generated, queued, processing, completed, failed and cancelled
states; a labelled tone selector and visible focus. The completed view renders subject, greeting, summary and
only non-empty Decisions, Action Items and Open Questions sections, followed by
closing, confidence and generated time.

**Copy email** writes plain text to the browser clipboard. It does not copy
HTML and omits headings for empty sections. **Regenerate** requests another
draft using the selected tone. There is deliberately no Send control.

See [Unified Meeting Intelligence](unified-meeting-intelligence.md) for overall
state, aggregate API, progress, dependency orchestration and polling rules.

## Migration, tenancy, privacy and observability

Migration `0012_follow_up_email` widens AI job/artefact type constraints and
adds nullable `composition_tone` to jobs. A database check requires one of the
three tones for Follow-up Email jobs and requires null for every other job
type. Existing composite tenant keys, forced PostgreSQL RLS and explicit
repository organisation predicates remain unchanged. Trace guards make tone
immutable. Downgrade removes Follow-up Email rows before restoring the previous
constraints and drops the column, so application rollback and any necessary
data export must happen first.

Logs and audits contain only identifiers, lifecycle/type/version labels,
selected tone, provider trace, timing/token/cost values and content-free source
or output counts. They exclude email subject/body, source artefact content,
transcript, rendered prompt, raw/invalid output, participant details, secrets
and raw exceptions.

## Known limitations

- Draft quality is limited to the four validated source artefacts; missing or
  stale source intelligence prevents composition.
- A generic greeting and closing are used because recipient and sender details
  are outside the approved source boundary.
- Facts are preserved rather than rewritten, so source phrasing may not read as
  fully polished prose.
- There is no editing, recipient selection, send, Gmail/Outlook, CRM activity,
  approval workflow, streaming, WebSocket or background automation.
- The mock is deliberately narrow, prompts/schemas are code-deployed and cost
  uses the existing integer project convention.
- Production identity, consent, retention/export/erasure and operational
  controls remain incomplete; production customer data is prohibited.
