# AI

WO-004A1/A2 provide tenant-isolated persistence and internal job/artefact
services. WO-004B1 adds a durable worker; WO-004B2/B3 add the provider boundary,
versioned prompts and strict output validation. WO-004C1 uses those seams for
one customer-facing Executive Summary. WO-004C1A adds an optional server-side
OpenAI Responses API adapter while retaining the deterministic no-network mock
as the default. WO-004C2 adds an independent, strictly structured
transcript-grounded Decisions capability, WO-004C3 adds concrete committed
Action Items with conservative due-date handling, WO-004C4 adds strict
transcript-grounded Risks & Blockers, and WO-004C5 adds genuinely unresolved
Open Questions through the same stack. WO-004C6 adds the first customer-ready
composer: a Follow-up Email produced only from validated Executive Summary,
Decisions, Action Items and Open Questions artefacts plus an explicit tone. It
never reads or sends the transcript and deliberately excludes Risks & Blockers.
No later intelligence capability, send integration, Anthropic/Gemini provider,
embedding, tool use or agent is active.

See [AI domain services](../03-engineering/ai-domain-services.md), the
[AI worker queue](../03-engineering/ai-worker-queue.md) and
[AI provider abstraction](../03-engineering/ai-provider-abstraction.md) for the
implemented boundary. The
[OpenAI provider guide](../03-engineering/openai-provider-integration.md)
documents configuration, strict Responses API output and the external
transcript data flow. The
[prompt registry and structured-output guide](../03-engineering/prompt-registry-and-structured-output.md)
documents the WO-004B3 extension.
The [Executive Summary guide](../03-engineering/executive-summary-intelligence.md),
[Meeting Decisions guide](../03-engineering/meeting-decisions-intelligence.md)
the [Meeting Action Items guide](../03-engineering/meeting-action-items-intelligence.md)
and [Meeting Risks & Blockers guide](../03-engineering/meeting-risks-blockers-intelligence.md)
and [Meeting Open Questions guide](../03-engineering/meeting-open-questions-intelligence.md),
and the [Follow-up Email Composer guide](../03-engineering/follow-up-email-composer.md)
document the current Meeting Intelligence capabilities. The
[Unified Meeting Intelligence guide](../03-engineering/unified-meeting-intelligence.md)
documents their aggregate product state and orchestration without changing
prompt, schema, provider or artefact boundaries.

Future AI work must use the typed provider port, schema validation, authorised
minimum evidence, content-redacted logs, explicit model/prompt versions and
human approval for consequential output.

For the five transcript-grounded capabilities, OpenAI selection sends the
bounded selected meeting transcript to OpenAI. For Follow-up Email, it sends
only the validated customer-safe four-artefact projection and tone; the
composer never transmits transcript text. Production customer data remains
prohibited until production identity, consent, provider privacy/retention,
deletion and operational gates are approved.

The [AI system blueprint](ai-system-blueprint.md) defines the target components, safeguards, evaluation, observability, cost and latency boundaries through beta. It is architecture documentation, not implementation.
