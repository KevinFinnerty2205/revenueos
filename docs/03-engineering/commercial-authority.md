# Commercial authority

- **Status:** Implemented by WO-047; test billing facts added by WO-048
- **Migration:** `0052_commercial_plans_trial`
- **Billing:** Provider-neutral architecture and test mode implemented by WO-048; live disabled
- **Credits:** Not implemented

## Authoritative catalogue

The API owns one immutable V1 catalogue. It is internal and must not be published as
final market pricing without separate approval.

| Plan       | Monthly | Annual | Included active users | Included modules                      |
| ---------- | ------: | -----: | --------------------: | ------------------------------------- |
| Core       | AUD 200 | AUD 2,000 | 5                  | Core                                  |
| Growth     | AUD 350 | AUD 3,500 | 10                 | Core, Prospect, Engage                |
| Complete   | AUD 500 | AUD 5,000 | 15                 | Core, Prospect, Engage, Create, CRM   |
| Enterprise | Custom  | Custom | operator-approved      | Core, Prospect, Engage, Create, CRM   |

`CRM` means supported external CRM connectors. Native CRM, Native Pipeline and the
canonical Account/Contact/Opportunity workflow remain part of Core. An operator may
assign Prospect, Engage, Create or CRM as an add-on to another base plan; WO-047 sets
no public add-on price.

## Domain model

- `commercial_plan_versions` stores immutable global plan snapshots. A deterministic
  UUID identifies each code/version, so later price changes require a new version.
- `organisation_commercial_states` stores the tenant's selected plan version,
  commercial status, billing interval label, trial dates, optional Enterprise user
  limit, add-ons, over-limit state, effective time, operator metadata and optimistic
  `lock_version`.
- `organisation_module_entitlements` is the existing tenant capability boundary,
  extended with `none`, `read` and `write` access plus plan/trial/add-on provenance.
- `commercial_state_events` is an immutable tenant-scoped history snapshot containing
  the effective plan, entitled and readable modules, seat count/limit, trial dates,
  actor, reason and state version.

Plan contents never come from the browser. `GET /api/v1/commercial` returns the
active organisation's safe projection to an active administrator. There is no
plan/trial mutation HTTP endpoint. The separate admin-only billing routes accept
only a plan code and interval, validate them against this catalogue and let verified
billing facts call this authority; billing never calculates entitlements itself.

## Trial and state transitions

Trial start is an explicit support operation. It may replace the unused provisioned
Core baseline, grants the Complete profile for 14 days, requires no card and cannot
automatically charge. `trial_used_at` permits only one trial per organisation.

```text
explicit start -> trial_active (14 days) -> grace (30 days) -> expired
                         |                         |
                         +---- operator assigns an active plan ----+
```

The exact trial-end instant begins grace. The exact grace-end instant expires
access. Grace retains read/export access but blocks new mutations and external work.
Expired, inactive and suspended state fail closed. No transition deletes customer
data or attempts payment.

## Effective access and downgrade

Effective access is the intersection of current commercial state, stored module
access, application/provider availability, organisation policy and user permission.
Entitlement does not prove that a provider is configured or live. The commercial
projection therefore reports `commerciallyIncluded`, `accessLevel` and
`operationalStatus` separately.

Plan assignment translates the base plan plus add-ons into tenant entitlements. A
removed module becomes `read` when historical access existed; new work is denied,
retained data stays readable/exportable and no purge occurs. Engage downgrade halts
active campaign progression and cancels queued/retryable external execution. Mock
email execution requires Engage; mock CRM and live HubSpot execution require CRM
connector access; Core calendar/task paths require Core. Connection creation/testing,
preview, confirmation, worker execution and reconciliation re-check the applicable
module. Revocation remains available as a safety action.

A write-authorisation check takes a shared lock on the commercial-state row for the
operation transaction. Plan changes take the conflicting update lock. This gives a
concurrent downgrade and new module operation one deterministic order: work already
authorised completes before the downgrade, while work requested behind the downgrade
observes the removed entitlement and fails closed. Workers still re-check access
before external execution.

## Included-user rule

An included user is an `active` organisation membership joined to an `active` user.
A pending invitation or identity without an active membership does not count;
disabled or removed membership does not count. Disabling a user does not delete their
historical authorship.

Core, Growth and Complete enforce 5, 10 and 15 users respectively. Enterprise
assignment requires a positive manual limit. The organisation row and commercial
state are locked while a member is admitted, serialising concurrent attempts at the
boundary. Downgrading below the current count removes nobody: the state becomes
`requires_resolution`, existing users remain, and additional activation is blocked.

## Operator workflow

Run from the repository root with the approved environment and migration head:

```bash
uv --directory apps/api run python -m revenueos.operations commercial-inspect \
  --organisation-id ORGANISATION_UUID

uv --directory apps/api run python -m revenueos.operations commercial-start-trial \
  --organisation-id ORGANISATION_UUID \
  --expected-lock-version VERSION \
  --operator-reference SUPPORT_REFERENCE \
  --reason "Approved reason" \
  --confirm "START TRIAL ORGANISATION_UUID"

uv --directory apps/api run python -m revenueos.operations commercial-assign-plan \
  --organisation-id ORGANISATION_UUID \
  --plan core --interval monthly \
  --expected-lock-version VERSION \
  --operator-reference SUPPORT_REFERENCE \
  --reason "Approved reason" \
  --confirm "ASSIGN CORE TO ORGANISATION_UUID"

uv --directory apps/api run python -m revenueos.operations commercial-change-state \
  --organisation-id ORGANISATION_UUID \
  --state suspended \
  --expected-lock-version VERSION \
  --operator-reference SUPPORT_REFERENCE \
  --reason "Approved reason" \
  --confirm "SET ORGANISATION_UUID SUSPENDED"
```

Inspect first, use the returned state version, supply a non-content actor reference
and reason, and retain the command result with the support case. Stale versions fail
rather than overwriting another operator. Enterprise additionally requires
`--custom-user-limit`; add-ons repeat `--add-on`.

## Security, lifecycle and recovery

Commercial state, events and entitlements have explicit organisation predicates,
composite tenant keys where applicable, and forced PostgreSQL RLS using trusted
transaction-local tenant context. The runtime role must not bypass RLS. Plan rows and
commercial history have database immutability triggers; the approved organisation
deletion maintenance setting is the only event-deletion exception.

Export schema v32 includes the current plan snapshot, commercial history, module
entitlements and safe billing projections. Billing records may require statutory
retention, so organisation deletion now refuses to remove an organisation with a
billing account until an approved accounting retention/disposal procedure exists. A
downgrade, expiry or payment event never deletes customer data. Logs and events
contain commercial metadata, not customer content, tokens, card data or provider
payloads.

WO-048 test billing consumes this authority through a separate provider adapter.
Verified active subscription facts can assign a paid plan with source
`billing_provider`; provider-only status cannot grant modules. Past-due status is an
attention state and does not invent a dunning/access rule. Scheduled cancellation
keeps paid access through the current period; verified terminal cancellation makes a
billing-provider-managed commercial state inactive without deletion. There is no
live billing, final tax/proration/refund policy, Credits ledger, allowance, pack,
expiry or top-up. See [Billing and subscription operations](billing-subscription-operations.md).
