# AI

Genuine AI execution is not currently implemented. WO-004A1/A2 provide tenant-isolated persistence and internal job/artefact services. WO-004B1 adds a durable worker that runs only a deterministic, no-network `infrastructure_test`. No OpenAI call, provider, prompt, embedding, transcript analysis, tool use or agent is active.

See [AI domain services](../03-engineering/ai-domain-services.md) and the [AI worker queue](../03-engineering/ai-worker-queue.md) for the implemented boundary.

Future AI work must use typed provider adapters, schema validation, authorised evidence, content-redacted logs, explicit model/prompt versions and human approval for consequential output.

The [AI system blueprint](ai-system-blueprint.md) defines the target components, safeguards, evaluation, observability, cost and latency boundaries through beta. It is architecture documentation, not implementation.
