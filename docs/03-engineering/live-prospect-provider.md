# Live Prospect provider boundary

WO-050 adds a provider-neutral production execution boundary and a dormant Apollo
adapter. Production-capable does not mean production-active: current production
configuration still prohibits Credits and therefore cannot enable paid Prospect work.

## Flow

`server quote → customer confirm → idempotent reserve → queue and bind → recheck policy and kill switches → mark executing → provider call → validate/map → persist provenance → settle/release → finalise`

The Prospect action UI obtains a server-owned WO-049 quote and shows the action,
quantity, maximum Credit cost, balance and pinned pricing notice before confirmation.
Confirmation sends the quote plus a stable idempotency key to the Prospect endpoint;
the server idempotently reserves the quote and then binds the resulting operation to
the new run. If queueing is rejected before execution, the unused reservation is
released. An external company run requires
`PROSPECT_COMPANY_RESEARCH`; a person run requires `PROSPECT_PERSON_RESEARCH`. A
composite tenant foreign key and one-run-per-operation constraint preserve the link.
Unrelated, stale or requester-mismatched reservations cannot be consumed, and an
unused supplied reservation is released if freshness, concurrency or idempotency
prevents a new run. Search by a seller-supplied domain is local and creates no hidden
Apollo search spend.

The adapter implements organisation enrichment, zero-Credit people search and person
match with personal email and phone reveal off. It uses a fixed official HTTPS origin,
bounded timeouts/body size, one bounded 429 retry and allow-listed strict response
models. The current Apollo POST endpoints receive documented query parameters rather
than a JSON body. People Search's obfuscated surname is retained as ambiguous staging
identity only; a person match must return the requested provider ID and the target
company's domain before full identity or current-employment fields are accepted.
Company enrichment must likewise match the requested domain. A People Search hit for
a previous employer is discarded unless its current organisation matches the target.
Unknown fields are ignored; missing/changed required fields fail visibly. Raw payloads
and provider errors never cross the adapter. A stable Oryntela request ID is sent as
correlation metadata; Apollo does not document request idempotency, so an ambiguous
response is not retried.

## Outcomes and recovery

- `completed` and `partial`: sourced observations persist, reported successful units
  settle and unused reservation releases.
- `no_result`: no sources/assertions are invented; zero successful units are recorded.
- definite non-execution: reservation releases and the run fails safely.
- timeout/ambiguous 5xx/malformed billable response: operation and run become
  `unknown`; no automatic retry.
- stale worker lease before execution: safe retry under the same reservation.
- stale lease after `executing`: both records become `unknown` for reconciliation.
- a validated external result persists before settlement. If the worker stops after
  settlement, recovery finalises that persisted result without another provider call;
  if it stops before the outcome is knowable, recovery uses `unknown` rather than a
  blind retry.

The existing WO-049 reconciliation service is authoritative. In-flight reconciliation
remains allowed after a kill switch is disabled; new execution does not.

## Data and trust

Migration `0055_live_prospect_provider` adds execution metadata to the existing
tenant-owned research run rather than a parallel provider-fact store. It pins the
Credit operation, stable request ID, provider mode/outcome/units/cost and approved
Selling Profile revision. Existing forced RLS and tenant predicates cover the table.

Apollo fields map only to existing company/person sources, observations, roles and
business contact candidates. Structured provider data is `provider_supplied`, never
`verified`. The provider attribution page is used when there is no inspectable source;
record IDs never fabricate URLs. Business email is retained only for the researched
company domain and generic shared mailboxes such as `info@`, `sales@` and `support@`
are rejected in both adapter mapping and provider-neutral validation. Phone is
discarded. Existing contactability, suppression, promotion, merge, export and deletion
boundaries remain authoritative.

Only the approved Selling Profile present when a run is queued is pinned. Draft and
retired profiles are ignored. The profile is never sent as provider instructions.
After sourced results validate, it may add an explicitly `inferred` Potential
Relevance observation that names the offering and says it is not customer Evidence.
It cannot create Evidence, Opportunity truth, Methodology confirmation or a confirmed
decision-maker role.

## Readiness

The administrator projection reports `UNCONFIGURED`, `READY`, `DEGRADED` or
`DISABLED` without a paid API health call. External execution requires all of:

- explicit provider selection and credential;
- external-provider and Credits feature flags;
- owner provider approval, terms/licence approval and privacy approval;
- a current provider-health reference from an authorised zero-cost check;
- a versioned provider cost model;
- production Credit action-price approval and owner margin policy;
- for Apollo company enrichment, requested-unit charging with an explicit no-result
  pricing notice so a provider-charged miss cannot become hidden Oryntela-funded usage;
- bounded organisation exposure/provider-cost caps and enabled global/action/provider
  controls both in readiness and again at execution.

Missing configuration fails startup or execution closed. Production never falls back
to deterministic data. The adapter is replaceable; provider-neutral facts, Credit
history and promoted canonical Sales records can survive provider disablement subject
to the signed retention/licensing terms.

## Test boundary

CI uses synthetic minimal fixtures and never calls Apollo. Tests cover exact request
shape, entity/domain/current-employment matching, obfuscated discovery identity,
mapping, unknown extra fields, missing schema, no result, timeout, bounded rate
limiting, oversized response, safe errors, email/phone minimisation, quote/reserve/run
binding, insufficient-Credit denial, partial settlement, unused reservation release,
unknown reservation retention, worker interruption recovery, tenant ownership through
composite keys, approved-profile pinning and inert prompt-like provider text. The TEST
action prices remain visibly non-production and no live cost is recorded.
