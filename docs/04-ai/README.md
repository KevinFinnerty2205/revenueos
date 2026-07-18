# AI

Genuine external-model execution is not currently implemented. WO-004A1/A2 provide tenant-isolated persistence and internal job/artefact services. WO-004B1 adds a durable worker; WO-004B2/B3 add the deterministic provider boundary, versioned prompts and strict output validation. WO-004C1 uses those seams for one customer-facing Executive Summary from the current transcript, but generation remains deterministic, zero-network mock output. No OpenAI/Anthropic/other external call, real credential, embedding, tool use or agent is active.

See [AI domain services](../03-engineering/ai-domain-services.md), the
[AI worker queue](../03-engineering/ai-worker-queue.md) and
[AI provider abstraction](../03-engineering/ai-provider-abstraction.md) for the
implemented boundary. The
[prompt registry and structured-output guide](../03-engineering/prompt-registry-and-structured-output.md)
documents the WO-004B3 extension.
The [Executive Summary guide](../03-engineering/executive-summary-intelligence.md)
documents the only current Meeting Intelligence capability.

Future AI work must use the typed provider port, schema validation, authorised
minimum evidence, content-redacted logs, explicit model/prompt versions and
human approval for consequential output.

The [AI system blueprint](ai-system-blueprint.md) defines the target components, safeguards, evaluation, observability, cost and latency boundaries through beta. It is architecture documentation, not implementation.
