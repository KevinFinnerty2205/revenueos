# WO-050 — Live Prospect Provider

- **Branch:** `codex/wo-050-live-prospect-provider`
- **Baseline:** `8a49f52c67f8944708ce17e2548aa59088e86db6`
- **Status:** implemented; awaiting engineering review
- **Migration:** `0055_live_prospect_provider`
- **Provider:** Apollo production-capable adapter; not production-active
- **Data/spend:** synthetic fixtures and public documentation only; AUD $0

## Outcome

WO-050 connects the existing Prospect and WO-049 Credit domains without activating a
provider. Live runs require a same-tenant, same-requester reserved action, pin the
approved Selling Profile revision, and recheck entitlement, Credits, cost exposure and
kill switches immediately before execution. Definite non-execution releases; success
settles; ambiguous outcomes remain reserved for reconciliation without blind retries.

The Apollo adapter maps bounded company/person/business-email fields into existing
source, observation, person, role and contact-candidate models. It never requests
personal email or phone reveal, never stores raw payloads and never upgrades structured
provider data to verified/customer truth. People search is bounded; company browsing
starts from a seller-supplied domain to avoid hidden provider search cost.

## Product and data boundary

The admin UI exposes honest readiness/activation blockers plus no-result and unknown
states at desktop and 390 px. Existing review, source click-through, duplicate checks,
contactability and deliberate Account/Contact promotion remain in place. Engage
sending, SMS, voice, CRM connectors, Microsoft, Google, ABR/ASIC and automatic
enrichment remain out of scope.

The database audit found no missing core customer entity. It found one provider-run
metadata gap, closed in migration 0055 with Credit operation, Selling Profile
revision, provider mode/request/outcome/units and cost references. Existing major
types remain Organisation/User/Membership, Selling Profile, Company, Contact,
Opportunity, Task, Interaction/Meeting/Evidence, Prospect Target Market/company/person
research, Commercial/Billing/Credits and AI job/artefact domains.

Authorised export schema 34 adds the portable Credit-operation, Selling Profile
revision, provider mode/outcome and unit links. Provider costs, credentials, worker
leases and raw payloads remain excluded.

## Provider and commercial boundary

Apollo standard plans do not permit powering an external product or sharing data with
customers. A separate written agreement with custom pricing/terms is required. Exact
cost, billing, renewal and production data rights are therefore unknown. No account,
trial, card, subscription, provider unit or external smoke test was authorised.

There are no production Credit prices, packs or margin floor. Test prices prove only
the quote/reserve/settle machinery. Candidate 50/60/70% margins are recorded as exact
formulas against future approved maximum cost, not activated prices.

## Verification scope

Automated tests cover adapter success/person/no-result, unknown schema fields, removed
required fields, timeout, rate limit, safe rejection, body cap, phone exclusion,
business-email domain control, inert adversarial text, Credit-required queueing,
success settlement, unknown held reservation, approved/draft Selling Profile pinning,
existing Prospect tenant/provenance/promotion/security regressions, settings UI and
responsive outcome states. PostgreSQL RLS and migration gates remain part of the full
repository validation.

## UI evidence

- [Synthetic company research — desktop](assets/wo-050-prospect-company-desktop.png)
- [Synthetic company research — 390 px](assets/wo-050-prospect-company-mobile-390.png)
- [Synthetic decision-maker research — desktop](assets/wo-050-prospect-person-desktop.png)
- [Synthetic decision-maker research — 390 px](assets/wo-050-prospect-person-mobile-390.png)
- [Desktop provider readiness](assets/wo-050-prospect-provider-readiness-desktop.png)
- [390 px provider readiness](assets/wo-050-prospect-provider-readiness-mobile-390.png)

## Explicit boundary

Production provider activation, provider contract acceptance, production Credit
pricing, real customer data and WO-040 are not started. See
[provider qualification](../05-integrations/prospect-live-provider-qualification.md),
[economics](../04-commercial/oryntela-prospect-provider-economics.md) and
[engineering boundary](../03-engineering/live-prospect-provider.md).
