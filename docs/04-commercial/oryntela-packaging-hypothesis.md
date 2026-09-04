# Oryntela packaging hypothesis

- **Status:** Modules are established; plan composition is partly undecided
- **Consolidated:** 4 September 2026
- **Implementation:** Manual entitlements exist; subscription/billing packaging does not

## Plans and modules are different

A **plan** is a commercial package a customer buys. A **module** is a product
capability area.

| Product modules                                | Commercial plans                   |
| ---------------------------------------------- | ---------------------------------- |
| Core foundation, Prospect, Engage, Create, CRM | Core, Growth, Complete, Enterprise |

Core is both the established product-foundation name and the entry plan name. That is
acceptable when copy says **Core plan** or **Core experience**. Complete is only a
plan/bundle; there is no Complete module. Do not invent another tier name merely to
avoid this manageable context distinction.

## Current hypothesis

| Plan       | Direction                                                                                                                                                                      | Composition status                                                   |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| Core       | Sales Brain, Interactions, Evidence, Revenue Brain, Methodology, Home, Actions, Accounts/People/Opportunities, Pipeline, Analytics, Targets, Forecast and Manager Intelligence | Direction established; final public feature list not approved        |
| Growth     | Core plus a coherent selection of expansion capability                                                                                                                         | **UNDECIDED — validate**                                             |
| Complete   | Core plus the validated end-to-end expansion bundle                                                                                                                            | Intended to include all relevant modules; final matrix **UNDECIDED** |
| Enterprise | Larger-team, contractual and approved governance/integration needs                                                                                                             | Custom; do not claim SSO/SCIM or features not built                  |

Customers should be able to buy contextual add-ons such as Core + Create, Core +
Prospect or Core + CRM where validated. They should not be forced into Complete for
one required workflow. Add-on prices are undecided.

## Entitlement boundary

The existing server-authoritative feature flags/manual entitlements prove availability
architecture, not commercial subscription enforcement. Future availability should be
derived from product capability, plan/module entitlement, organisation policy, user
permission, provider health and Credits where applicable. A client route or price
label never grants access.

Downgrade/payment failure should preserve readable customer data under retention and
export policy. Trust, provenance, correction, accessibility, security and data
export/deletion are not premium features.

## Contextual discovery

Do not fill navigation with disabled products or advertising. Show one calm suggestion
where the existing workflow exposes the need:

- qualified-pipeline gap -> Prospect;
- reviewed outreach need -> Engage;
- customer presentation/business case -> Create;
- simple system-of-record need -> CRM.

Explain the outcome and current alternative. Show a price only after approval.

## Credits remain separate

Plan/module ownership grants software capability. Credits fund selected metered
external operations. Complete does not imply unlimited Credits, and Credits do not
unlock a module. This separation protects customer clarity and Oryntela economics.

## Decisions still required

- exact Growth bundle and upgrade reason;
- exact Complete module matrix;
- individual add-on eligibility and prices;
- included-user/extra-user bands;
- trial entitlement matrix;
- module/plan treatment after downgrade; and
- billing and entitlement implementation.
