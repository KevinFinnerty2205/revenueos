# AI

AI execution is not currently implemented. WO-004A1 and WO-004A2 provide only tenant-isolated persistence plus internal repositories/services for idempotent `infrastructure_test` jobs, lifecycle validation, strict test artefacts and metadata-only audits. No worker, OpenAI call, provider, prompt, embedding, transcript analysis, tool use or agent is active.

See [AI domain services](../03-engineering/ai-domain-services.md) for the implemented boundary.

Future AI work must use typed provider adapters, schema validation, authorised evidence, content-redacted logs, explicit model/prompt versions and human approval for consequential output.

The [AI system blueprint](ai-system-blueprint.md) defines the target components, safeguards, evaluation, observability, cost and latency boundaries through beta. It is architecture documentation, not implementation.
