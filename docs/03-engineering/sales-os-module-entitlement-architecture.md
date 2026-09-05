# Sales OS module entitlement architecture

- **Status:** Implemented commercial authority through WO-047
- **Migration:** `0052_commercial_plans_trial`
- **Principle:** Core stays coherent; commercial inclusion, runtime availability,
  organisation policy and user permission remain separate facts

## Plans and modules

| Plan       | Included users | Included modules                            |
| ---------- | -------------: | ------------------------------------------- |
| Core       | 5              | Core                                        |
| Growth     | 10             | Core, Prospect, Engage                      |
| Complete   | 15             | Core, Prospect, Engage, Create, CRM         |
| Enterprise | Manual         | Core, Prospect, Engage, Create, CRM         |

The immutable internal V1 prices are documented in
[Commercial authority](commercial-authority.md). A plan is a commercial package; a
module is a capability boundary. `CRM` means supported external CRM connectors.
Native CRM, Native Pipeline and canonical sales records are Core. Prospect, Engage,
Create or CRM may also be operator-assigned add-ons; add-on prices do not exist.

## Authoritative evaluation

```text
effective availability
  = commercial state and module access
  ∩ system/provider capability
  ∩ organisation configuration/policy
  ∩ active membership and user permission
```

`organisation_commercial_states` selects an immutable
`commercial_plan_versions` row and optional add-ons. Plan assignment translates
that selection into the existing `organisation_module_entitlements` rows. Each row
has `none`, `read` or `write` access and plan/trial/add-on provenance. The client
cannot grant access by changing route, local state or request data.

The admin projection deliberately returns three distinct values per module:

- `commerciallyIncluded`: in the selected base plan or current add-ons;
- `accessLevel`: effective `none`, `read` or `write`, including grace/downgrade; and
- `operationalStatus`: `available`, `mock_only` or `unavailable` from deployment and
  provider configuration.

An entitlement therefore does not claim that a paid provider is live. Prospect may
remain mock-only, Engage simulation-only and CRM connectors unavailable even on a
Complete plan. Core product capabilities do not depend on those providers.

## Current enforcement

Every business API first requires effective Core access. Grace permits reads/export
but blocks mutations. Expired, inactive and suspended organisations fail closed.
Module services and workers then enforce their own entitlement:

- Prospect: target-market, account/person discovery, research, review and promotion;
- Engage: outreach, Campaigns/Sequences and Events;
- Create: templates, presentations, approvals/downloads and Business Cases; and
- CRM: external HubSpot connection, mapping, preview, confirmation, worker execution
  and reconciliation.

Native CRM settings, custom fields, archive/restore, imports, merges and Native
Pipeline administration require Core write access, the existing native feature
flags, appropriate admin authority and Native CRM mode. External mode additionally
requires CRM connector write access.

Legacy module-toggle endpoints are retained only as explicit denials with
`commercial_plan_managed`; an organisation administrator is not a commercial
operator. `GET /api/v1/commercial` is admin-only and read-only. Operator mutation is
outside the browser and requires exact confirmation, actor/reason and optimistic
state version.

## Trial and downgrade

An explicit trial grants the Complete module profile for 14 days. At its exact end,
all previously accessible modules become read-only for 30 days; at grace end access
becomes `none`. There is one trial per organisation, no card and no automatic charge.

When a paid/admin-approved plan removes a module, an existing entitlement becomes
`read` instead of being erased. New module work is blocked immediately, historical
data stays in normal authorised reads/export and no customer data is purged.
Re-upgrade restores write access without reconstructing records. Engage downgrade
halts active work and cancels safe queued/retryable execution. Already executing
irreversible provider work follows its established reconciliation contract.

## User limit

Only an active organisation membership joined to an active user consumes a seat.
Pending identities/invitations, disabled members and removed memberships do not.
The organisation and commercial state are row-locked while admission is evaluated,
so concurrent final-seat attempts serialise. Downgrading below the active count
marks `requires_resolution`, preserves every person and blocks additional admission.

## Storage, RLS and history

Plan versions are global immutable catalogue rows. Commercial state, module
entitlements and commercial events are tenant scoped. Repository operations include
organisation predicates; PostgreSQL forced RLS uses the trusted transaction-local
tenant setting. Commercial events are immutable snapshots containing the plan
version, entitled/readable module sets, status, dates, seats, actor, reason and state
version. Stale operator writes fail with no last-writer-wins overwrite.

Export schema v32 includes current commercial state with its immutable plan snapshot,
commercial history and module entitlements. Approved organisation deletion removes
them. Expiry and downgrade never do.

## UX rules

Ordinary sellers receive short product language such as “Prospect isn't included in
your organisation's current plan”; they do not see internal entitlement codes or
prices. Admin Settings shows plan, status, interval, trial/grace dates, users and
module/provider distinction. It has no purchase, card, invoice or trial-date control.
Navigation represents user goals, not a pricing grid.

## Explicit boundary

WO-047 adds no Stripe, checkout, webhook, subscription-provider mapping, card,
invoice, GST, proration, refund, payment failure, extra-user price or automatic
renewal. It adds no Credits ledger or allowance and activates no provider. Those are
separate future decisions and must reuse this authority rather than create another
entitlement system.

See [Commercial authority](commercial-authority.md) and
[ADR 0069](../08-decisions/0069-versioned-commercial-authority.md).
