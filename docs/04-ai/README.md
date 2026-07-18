# AI

WO-004A1/A2 provide tenant-isolated persistence and internal job/artefact
services. WO-004B1 adds a durable worker; WO-004B2/B3 add the provider boundary,
versioned prompts and strict output validation. WO-004C1 uses those seams for
one customer-facing Executive Summary. WO-004C1A adds an optional server-side
OpenAI Responses API adapter while retaining the deterministic no-network mock
as the default. No additional intelligence capability, Anthropic/Gemini
provider, embedding, tool use or agent is active.

See [AI domain services](../03-engineering/ai-domain-services.md), the
[AI worker queue](../03-engineering/ai-worker-queue.md) and
[AI provider abstraction](../03-engineering/ai-provider-abstraction.md) for the
implemented boundary. The
[OpenAI provider guide](../03-engineering/openai-provider-integration.md)
documents configuration, strict Responses API output and the external
transcript data flow. The
[prompt registry and structured-output guide](../03-engineering/prompt-registry-and-structured-output.md)
documents the WO-004B3 extension.
The [Executive Summary guide](../03-engineering/executive-summary-intelligence.md)
documents the only current Meeting Intelligence capability.

Future AI work must use the typed provider port, schema validation, authorised
minimum evidence, content-redacted logs, explicit model/prompt versions and
human approval for consequential output.

OpenAI selection sends the bounded selected meeting transcript to OpenAI.
Production customer data remains prohibited until production identity, consent,
provider privacy/retention, deletion and operational gates are approved.

The [AI system blueprint](ai-system-blueprint.md) defines the target components, safeguards, evaluation, observability, cost and latency boundaries through beta. It is architecture documentation, not implementation.
