# Next Best Action Intelligence

## Product behaviour

WO-006D adds a meeting-scoped **Next Best Action** composer. After all eight
current-version Meeting Intelligence extractions are validated, RevenueOS
returns one overall recommendation, its priority and confidence, concise
reasoning and at most five ordered recommended actions. Each action includes a
reason, priority, confidence and explicit source dependencies.

The capability recommends only. It does not create a CRM update, email, task or
automation, invoke an integration, or trigger any action. It does not provide a
win probability, forecast or deal score.

## Hard source boundary

Next Best Action uses exactly these eight validated, persisted artefacts:

- Executive Summary;
- Buying Signals;
- Objections & Competitive Signals;
- Stakeholder Intelligence;
- Decisions;
- Action Items;
- Open Questions; and
- Risks & Blockers.

Follow-up Email is deliberately not a source. The request service and worker
independently require one same-tenant, same-meeting, same-transcript-version
artefact of every type, with the current code-deployed prompt and schema
versions. The worker loads artefact JSON and content-free transcript audit
metadata only. It never queries transcript text.

`NextBestActionProviderInput` cannot carry a transcript. Prompt v1 has exactly
eight JSON variables matching the list above. When OpenAI is selected, those
validated artefacts are the only customer content sent for this operation.

```text
eight validated artefacts
          │
          ▼
tenant/version trace validation
          │
          ▼
next_best_action prompt/schema v1
          │
          ▼
mock or OpenAI provider
          │
          ▼
strict schema + exact-reference grounding
          │
          ▼
append-only Next Best Action artefact
```

## Schema and grounding

The authoritative frozen schema is `NextBestActionArtifactContent`:

```json
{
  "overall_recommendation": "Identify the economic buyer.",
  "priority": "high",
  "confidence": 0.94,
  "reasoning": [
    "Buying Signals: decision_maker_missing.",
    "Stakeholders: economic_buyer:not_identified."
  ],
  "recommended_actions": [
    {
      "action": "Identify the economic buyer.",
      "reason": "Buying Signals: decision_maker_missing. Stakeholders: economic_buyer:not_identified.",
      "priority": "high",
      "confidence": 0.94,
      "depends_on": ["buying_signals", "stakeholders"]
    }
  ]
}
```

Every field is required and unknown fields are rejected. Priority is exactly
`high`, `medium` or `low`; confidence must be finite and between 0 and 1.
Recommendations are unique, bounded to five and ordered by importance. The
overall recommendation and priority must match the first action.

Dependencies are limited to `buying_signals`, `stakeholders`, `risks`,
`open_questions` and `action_items`. Each declared dependency must be supported
by an exact value from that artefact in the action reason. Every reasoning item
must likewise cite a value from one of the eight validated sources. This
application-side grounding check runs after strict schema validation and before
persistence.

## Lifecycle and APIs

`POST /api/v1/meetings/{meetingId}/intelligence/next-best-action` returns `202`
for a new queued job and `200` when equivalent pending, running or completed
work is reused. Equivalence includes organisation, meeting, pinned transcript
trace, source artefact versions, job type and prompt/schema versions. Failed or
cancelled work may be retried.

`GET /api/v1/meetings/{meetingId}/intelligence/next-best-action` returns
`empty`, `queued`, `running`, `completed`, `failed` or `cancelled`, safe
timestamps and message fields, generation availability and completed content.
It excludes source content, transcript, prompts, raw errors, worker/lease state
and provider payloads.

The unified generate endpoint queues Next Best Action and Follow-up Email only
after their respective source sets are ready. Next Best Action appears after
Stakeholders in the unified workspace and uses the existing single polling
chain. The completed view shows Overall Recommendation, Reasoning, Recommended
Actions, Priority and Confidence. It has no action, approval, CRM, task,
automation or email control.

## Providers, persistence and observability

Prompt, schema, job and artefact key/version are `next_best_action`/`1`.
`DeterministicMockAIProvider` returns stable recommendation scenarios for
missing economic-buyer/decision-maker coverage, technical risk, weak next
steps, high-priority questions and material blockers. OpenAI explicitly
allowlists the typed operation while `infrastructure_test` remains prohibited.
Both providers use strict structured output; automated tests make no real
OpenAI request.

Migration `0016_next_best_action` widens the constrained job and artefact type
allowlists. Existing composite tenant keys, explicit organisation predicates,
forced PostgreSQL RLS, immutable trace guards and append-only artefact rules
remain unchanged. Downgrade deletes only Next Best Action jobs/artefacts before
restoring the prior constraints, so the previous application and workers must
be deployed first.

Logs and audits contain identifiers, lifecycle/type/version labels, safe
counts and ordinary provider timing/token/cost metadata. They exclude
transcript, source artefact content, recommendation priority/confidence,
recommendations, reasoning, rendered prompts, raw/invalid provider output and
raw exceptions.

## Known limitations

- All eight current-version source artefacts must exist and validate.
- Recommendations describe only the supplied meeting intelligence; there is no
  account history, CRM context, enrichment or cross-meeting memory.
- The dependency taxonomy is intentionally narrow and schema v1 is
  code-deployed.
- There is no edit/approval flow or operational execution.
- Production identity, consent, retention/export/erasure and operational
  controls remain incomplete; production customer data is prohibited.
