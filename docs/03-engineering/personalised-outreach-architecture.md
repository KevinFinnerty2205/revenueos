# Engage personalised outreach architecture

## Implemented boundary

WO-029 adds a tenant-isolated Engage slice to the existing FastAPI/Next.js modular
monolith. It reuses canonical `Company`, `Contact`, `User`, Prospect provenance,
Action review and the Execution Foundation. No service, queue, datastore, provider
SDK or browser-to-database path was added.

The public recipient boundary accepts only a Contact UUID from the authenticated
organisation. Server code resolves the current Contact email and provenance. Draft,
edit, approval, preview and confirmation contracts never accept an arbitrary
recipient or From address. The sender is the current user and execution requires that
user's active sender-bound Email connection.

## Domain and persistence

Migration `0038_personalized_outreach` introduces:

| Table                              | Responsibility                                                                                    |
| ---------------------------------- | ------------------------------------------------------------------------------------------------- |
| `outreach_policies`                | one administrator-controlled Engage policy per organisation                                       |
| `outreach_messages`                | mutable aggregate state, canonical Contact/sender/Action references and current/approved revision |
| `outreach_versions`                | immutable exact sender, recipient, seller context, copy, plan, composer and fingerprint           |
| `outreach_personalization_sources` | immutable references used by one exact version                                                    |
| `contact_suppressions`             | organisation-scoped HMAC identity, optional Contact link, controlled reason and restoration audit |

All new rows carry `organisation_id`; composite foreign keys preserve tenant scope.
Repository reads/writes contain explicit organisation predicates. PostgreSQL RLS is
enabled and forced on every new tenant table. `OutreachVersion` and its source rows
have database immutability guards on PostgreSQL and SQLite.

`action_proposals.opportunity_id` becomes nullable so a canonical Contact can own a
one-to-one outreach Action without inventing an Opportunity. Its new
`personalized_outreach` payload pins the outreach/version, sender identity, Contact,
address trust, subject and body. The matching Action revision remains immutable.

## Lifecycle and version/provenance model

1. Resolve entitlement, membership, Contact and organisation policy.
2. Evaluate contactability and select at most three eligible person plus three
   eligible company research observations from current completed runs.
3. Deterministically compose copy using only approved seller context and a recognised
   bounded hook; validate the result before persistence.
4. Create Action, Action version, outreach aggregate, outreach revision and only the
   exact sources actually used. The approved seller context is a separate reference.
5. An edit appends an immutable revision, copies source references, updates the
   matching Action version and clears every approval field.
6. Approval pins the current revision after fresh contactability, recipient and
   approved-seller-context snapshot checks.
7. Preview reads the approved Action revision, binds the current user connection and
   creates a short-lived fingerprinted execution preview.
8. Confirmation is idempotent and queues through the existing execution boundary.
9. The worker re-runs entitlement, active membership, sender, Contact, email, version,
   policy, suppression, cooldown and quota checks before adapter invocation.

Approval and confirmation are separate transactions. An approval audit explicitly
records `external_execution=false`. Logs contain IDs, purpose, revision, safe result
and source count—not email address, subject, body, source excerpt or provider payload.

## Personalisation and claim validation

Input research must belong to the promoted Contact's current Prospect Person and
current target. Only professional category allowlists are considered. Each
observation needs `verified` or `provider_supplied` trust and a supporting source.
Time-sensitive observations older than 365 days are excluded. Sensitive-term
observations are excluded before composition.

The deterministic composer recognises the synthetic Northstar expansion and
technology-consolidation observation keys. Other Contacts receive transparent
role/company/value copy. It does not have a generic free-form claim interpolation
path. The edit validator rejects deceptive subject prefixes/urgency, sensitive
language, fake following/mutual connection/personality framing and unsupported
percentage savings. This is a deliberately narrow v1 claim architecture, not a
general natural-language fact checker.

No AI provider is called. If an AI composer is later added it must receive bounded
source objects, return selected source IDs from that set plus strict structured copy,
and pass the same server validation. The provider may not fabricate citations.

## Contactability and suppression

`evaluate_contactability` computes one controlled state while returning address
trust separately. Checks include Engage entitlement and feature availability, active
sender membership, usable canonical email trust, active HMAC suppression, configured
policy, outbound enablement, provider-supplied permission, per-contact cooldown,
daily user/organisation limits and opt-out capability. Limits count only confirmed
personalised-outreach executions and exclude the current idempotent Action.

Suppression fingerprints are `HMAC-SHA256(deployment key, normalised email)` scoped
again by organisation in persistence/queries. The application never uses a plain
unsalted hash as the identity. Manual suppression may be restored by an authorised
administrator through the API boundary; recipient opt-out, complaint and permanent
bounce cannot be downgraded or restored through that boundary. There is no public unsubscribe
route until production sending supplies a proper link/event contract.

Deleting a Contact sets the outreach/suppression Contact references null and unlinks
the Prospect Person while preserving the fingerprint and minimum history. A later
Contact with the same normalised email in the same organisation remains suppressed.
Organisation deletion explicitly removes all outreach tables after cancelling
unsent executions/revoking connections. External email cannot be unsent.

## Execution, idempotency and delivery semantics

WO-029 uses `mock_email` only when environment is not production. Production
connection discovery and execution fail closed because no Gmail/Microsoft adapter is
registered. The adapter input is the exact approved payload; requests provide only
connection/preview IDs and confirmation.

The existing Execution Foundation provides unique preview confirmation and action/
revision/connection idempotency, attempt state, cancellation on revocation and safe
result messages. Simulation produces a deterministic mock object and no network
email. The model reserves `unknown_delivery_state`, but no reconciliation claim is
made: a future live adapter must persist provider receipt/message ID, distinguish
pre-acceptance retry from possible acceptance, honour `Retry-After`, and never blind
retry an ambiguous outcome.

There is no scheduling, tracking pixel, click redirect, open/click event, reply sync,
delivery guarantee or automatic follow-up. `submitted`/`sent` will mean only the
selected provider's documented acceptance semantics, not inbox delivery, unless an
authoritative delivery event exists.

## Retention, export and deletion

Private-beta export schema 19 includes outreach policy, aggregate/version content,
source references and suppression metadata intentionally. It excludes credentials,
raw HMAC keys and connector secrets. Existing retention removes old outreach
Actions/messages and cascaded versions/sources while active suppression persists.
Organisation deletion explicitly deletes policy, history and suppressions. Contact
deletion preserves minimal history/suppression as described above.

## API surface

- `GET /api/v1/engage/availability`
- `PATCH /api/v1/engage/admin/entitlement`
- `GET|PUT /api/v1/engage/policy`
- `GET /api/v1/engage/contacts/{contactId}`
- `POST /api/v1/engage/contacts/{contactId}/outreach`
- `GET|PATCH /api/v1/engage/outreach/{outreachId}`
- `POST /api/v1/engage/outreach/{outreachId}/approve`
- `POST|DELETE /api/v1/engage/contacts/{contactId}/suppression`
- `POST /api/v1/engage/outreach/{outreachId}/execution-preview`
- `POST /api/v1/engage/outreach/{outreachId}/send`

FastAPI/Pydantic remains the contract source. The shared TypeScript package contains
only the web-consumed response/payload surface.

## Operations and known limitations

Safe telemetry is metadata-only: contactability denial codes, state transition,
version, source count, execution mode and identifiers. No subject/body/address/source
excerpt is logged. Quotas default to private-beta caps and are narrowed by
organisation policy. No paid service was activated.

This architecture is one-to-one only. Campaigns, sequences, batches, arbitrary
recipients, inferred addresses, autonomous follow-up, scheduled delivery, production
mailbox OAuth, CRM activity logging and inbound replies are deferred.
