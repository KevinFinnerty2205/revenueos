# AI

Genuine AI execution is not currently implemented. WO-004A1/A2 provide tenant-isolated persistence and internal job/artefact services. WO-004B1 adds a durable worker; WO-004B2 routes its deterministic, no-network `infrastructure_test` through a typed mock-provider boundary. No OpenAI/Anthropic/other external call, real credential, prompt, embedding, transcript analysis, tool use or agent is active.

See [AI domain services](../03-engineering/ai-domain-services.md), the
[AI worker queue](../03-engineering/ai-worker-queue.md) and
[AI provider abstraction](../03-engineering/ai-provider-abstraction.md) for the
implemented boundary.

Future AI work must use the typed provider port, schema validation, authorised
minimum evidence, content-redacted logs, explicit model/prompt versions and
human approval for consequential output.

The [AI system blueprint](ai-system-blueprint.md) defines the target components, safeguards, evaluation, observability, cost and latency boundaries through beta. It is architecture documentation, not implementation.
