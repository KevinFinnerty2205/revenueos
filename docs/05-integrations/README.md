# Integrations

WO-018 adds a meeting-provider adapter contract and deterministic fake only. These
are extension/test boundaries, not a Teams, Zoom or Google Meet connection.

External integrations are not currently implemented. No CRM, ATS, email, calendar, meeting or payment provider is represented as connected; Supabase remains a planned production database/storage provider rather than proof of a configured deployment.

Future adapters require least-privilege credentials, explicit user authority, idempotency, receipts, reconciliation, audit and a real sandbox test before being called complete.

The [integration strategy](integration-strategy.md) defines provider value, data direction, source-of-truth, approval, authentication, recovery, deletion and phased rollout through beta.
