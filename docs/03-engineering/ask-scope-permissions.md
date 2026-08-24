# Ask RevenueOS scope and permissions

## Scope resolution

Scope is an explicit server contract, never inferred from a name in question text.

| Scope | Required identifier | Authorised retrieval |
| --- | --- | --- |
| Opportunity | Opportunity UUID | that organisation-scoped Opportunity and its current authorised related intelligence |
| Account | Company UUID | that organisation-scoped Company, its bounded Opportunities and company-level accepted Evidence |
| Workspace | none | open Opportunities owned by the active user, then related bounded intelligence |

Workspace requests carrying a scope ID and record scopes without a scope ID fail
contract validation. Cross-organisation IDs return the same safe not-found response
as missing records.

## Enforcement

The active organisation and user come only from verified authentication context.
The service rechecks active membership, repository queries include explicit
organisation predicates, and PostgreSQL transaction-local tenant context/RLS remains
defence in depth. Browser parameters can narrow scope but cannot choose an
organisation, owner or membership.

The current workspace definition is deliberately seller-owned rather than a broad
member-wide portfolio. Administrators do not gain an implicit cross-user Ask mode.
Adding manager/team scope would need a separate permission and product decision.

## Enumeration resistance

Capabilities resolves the same scope permissions as answering. Source IDs are
returned only from authorised retrieval. Telemetry accepts only an Ask request ID
already audited for the same organisation and user. No endpoint lists arbitrary Ask
sources, query plans or hidden tenant identifiers.

Organisation deletion cascades metadata audit events with the organisation. There is
no retained answer/conversation object to export or erase in WO-025B.
