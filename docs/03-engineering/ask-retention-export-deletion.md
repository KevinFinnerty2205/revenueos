# Ask RevenueOS retention, export and deletion

## Decision

WO-025B does not persist question text, answer text, source excerpts or conversation
history. Each submission is an independent request. Refreshing or leaving the page
removes the rendered answer, and follow-ups rerun bounded retrieval in the same
explicit scope.

Therefore Ask content adds no new retention class, export payload or deletion job.
Underlying Opportunity, Account, Evidence, interaction, Methodology, Revenue Brain,
Daily and Action records continue to follow their existing retention/export/deletion
rules.

## Persisted metadata

`BetaSystemEvent` stores answer-generated, source-opened and follow-up-selected events.
Answer-generation metadata is limited to organisation/user actor, opaque request ID,
scope type/ID, question class, answer status, source count, retrieval/composer names
and context-character count/latency. Interaction telemetry stores the opaque request/source
ID or a fixed selection label. It stores no question, answer, excerpt, transcript,
document/email body, prompt or provider payload.

These events are tenant-owned and cascade with organisation deletion. Existing
private-beta administrative export does not claim to export conversations because
none exist. If conversation persistence is proposed later, it requires a schema,
retention period, user-visible history/delete controls, export/erasure coverage,
legal/privacy review and new cross-tenant tests before launch.
