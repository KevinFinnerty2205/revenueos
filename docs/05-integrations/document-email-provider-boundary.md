# Document and email provider integration boundary

## Current state

WO-019 does not connect Gmail, Outlook, Google Drive, OneDrive, SharePoint or any
document system. Users upload one supported document or paste one email through a
first-party RevenueOS screen. Local and CI processing uses a deterministic
no-network mock. OpenAI is the only implemented extraction adapter and is disabled
unless explicitly configured.

## Adapter contract

The internal provider interface receives:

- a source UUID and kind;
- bounded extracted document fragments or normalised email text;
- server-derived source type, ownership/direction and provenance constraints; and
- a strict allowed evidence taxonomy and citation shape.

It returns strict-schema candidate statements and page/paragraph or message/line
locations. The adapter cannot set tenant IDs, Contact identity, source ownership,
support class, review state or downstream eligibility. `store=false` is used for
OpenAI requests. Provider request IDs may be retained for operational correlation;
payloads are not logged.

## Future connector requirements

A future mailbox or drive connector needs a separate work order and must provide:

1. explicit organisation-authorised OAuth installation with least scopes;
2. deliberate folder, thread or item selection—never blanket ingestion;
3. tenant-bound encrypted tokens behind an adapter, with revocation and permission
   re-checks before access and downstream use;
4. stable external IDs, version/change tracking and idempotent reconciliation;
5. source ACL, deletion, export, retention and residency behaviour documented for
   both RevenueOS and the upstream provider;
6. safe rate-limit, retry, webhook authenticity and connector-health handling;
7. no silent Contact creation and no sender identity without exact evidence; and
8. provider contract tests plus tenant, revocation and deletion regressions.

Until those controls are implemented and tested, `documentProviderImport` and
`emailProviderImport` remain false in capabilities and must not be described as
working integrations.
