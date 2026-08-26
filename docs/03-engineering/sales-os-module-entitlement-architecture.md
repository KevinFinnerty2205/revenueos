# Sales OS module entitlement architecture

- **Status:** WO-026/027 use one bounded Prospect organisation switch; the wider commercial model remains proposed
- **Principle:** Core remains coherent; module discovery is contextual and restrained

## Package model

The commercial catalogue contains RevenueOS Core, Prospect, Engage, Create and CRM;
RevenueOS Complete bundles them. Enterprise is a governance/support tier rather than
a feature-dumping ground. Actual prices and billing-provider implementation remain
future decisions.

## Effective availability

Current WO-026 availability is intentionally smaller than the target equation below:
the server combines the global Prospect feature flag, active tenant/membership,
organisation `prospect` entitlement and production-capable provider configuration.
Only admins can change the organisation switch. There is no billing, plan catalogue,
trial or grace-period model yet.

The server produces one product-safe availability projection:

```text
effective availability
  = commercial entitlement
  ∩ organisation policy
  ∩ system/provider capability
  ∩ user permission
```

The intersection is conceptual: the response distinguishes reasons rather than
reducing them to one boolean. A feature may be `available`, `setup_required`,
`permission_required`, `usage_limited`, `temporarily_unavailable` or `not_in_plan`.
Only authorised billing administrators receive commercial detail.

## Conceptual model

| Concept                          | Responsibility                                                |
| -------------------------------- | ------------------------------------------------------------- |
| `ProductModule`                  | Stable code, user-facing name and dependency on Core          |
| `PlanDefinition` / `PlanVersion` | Versioned package-to-capability mapping                       |
| `OrganisationSubscription`       | Effective plan, dates and commercial state                    |
| `EntitlementGrant`               | Capability, limit dimensions, source and effective period     |
| `OrganisationFeaturePolicy`      | Admin enable/disable and configuration prerequisite           |
| `CapabilityStatus`               | Runtime/provider availability independent of plan             |
| `UsageCounter`                   | Idempotent, period-scoped metered consumption where justified |
| `AvailabilityProjection`         | Safe response for a user/context with reason and next step    |

Except for the bounded `organisation_module_entitlements` Prospect row and usage
counters added by WO-026, these are future concepts. Plan mappings are versioned and
centralised; page code must never contain price or package rules. Tenant-owned state,
counts and keys include organisation scope.

## Server and client contract

API policy remains authoritative. Route/service authorisation checks the concrete
capability after verified tenant and membership resolution; hiding a button is not
security. The web app consumes a typed availability projection and renders consistent
states. It does not infer access from plan names or cache entitlements across
organisations.

Core APIs do not depend on an add-on. Add-on output may enrich a Core page through an
optional typed projection; its absence returns a valid Core response. Cross-module
links use stable canonical IDs rather than duplicate records.

## UX rules

- Purchased and configured: show the useful action in its natural place.
- Purchased but not configured: explain the required setup to an authorised user;
  other users get a simple unavailable state.
- No permission: explain who can help, without revealing restricted details.
- Temporarily unavailable: preserve readable Core state and offer retry/status.
- Not purchased: show a short contextual explanation only when the capability would
  directly answer the current question; do not add dead navigation or pop-ups.
- Usage limited: disclose unit, period and remaining availability before an action;
  never surprise the user after producing work.

Navigation represents user goals, not purchases. Find and Create may be hidden or
shown as a restrained discoverable destination depending on product policy, while
Sell/Pipeline/Home never become broken shells. Unavailable-module copy contains no
exact price unless it comes from an authorised commercial source.

## Changes, downgrade and failure

Entitlement changes are effective-dated, audited and idempotently applied. Upgrades
can reveal features after server confirmation. A downgrade stops new add-on actions
at the effective time but preserves authorised read/export access for a defined grace
and retention policy. It never deletes data synchronously or makes Core data
unreachable. In-flight jobs resolve under an explicit snapshot/cancellation policy.

Billing/provider outages do not silently grant new access or disable paid access on a
single transient failure. The service uses last-known confirmed commercial state for
a bounded period, alerts administrators and reconciles later. Manual grants require
reason, approver, expiry and audit.

## Usage dimensions to evaluate

Commercial discovery may evaluate per-user/team seats, research/contact credits, AI
usage, storage and execution volume. A dimension is adopted only when customers can
understand and predict it, it reflects real cost/value, and it does not discourage
safe Core use. Essential Sales Brain analysis and correction should not be metered
into dysfunction.

Counters use stable idempotency keys and adjustment history. Estimated tokens or
provider-specific internal units must not be exposed as if they were stable customer
value without a deliberate pricing decision.

## Security, privacy and operation

Entitlement administration requires least privilege and metadata audit. Commercial
state contains no payment credentials. Future Stripe integration belongs behind an
adapter and webhook verification boundary; Stripe is not required to implement the
entitlement domain. Responses reveal only the current organisation/user's safe state.

Cache keys include organisation, membership/role and entitlement version. Invalidate
on plan, policy, permission or capability changes. Metrics cover projection latency,
denials by safe reason, stale state and reconciliation—not user content.

WO-027 person discovery/research uses the same server-authoritative `prospect`
entitlement at list, discovery, research, review, promotion, delete and Contact-link
boundaries. A separate client flag was intentionally not added. Disabling Prospect
blocks person capability according to the same read/write policy; Core Accounts and
Contacts remain usable.

WO-029 introduces a distinct `engage` entitlement. Prospect entitlement or Contact
ownership alone cannot grant outreach. The API checks Engage at availability,
workspace, draft, edit, approval, preview, confirmation and worker execution. A
downgrade blocks new consequential operations immediately while retained outreach
content remains subject to export/retention policy. The current entitlement source is
manual private-beta administration; no billing integration or price is implied.

## Explicitly out of scope

WO-026/027 add no billing or plan table. Exact prices,
contracts, tax, invoicing, proration, trials and payment flows require later commercial
and legal decisions.
