# Oryntela packaging hypothesis

- **Status:** V1 plan composition implemented as internal commercial authority
- **Consolidated:** 4 September 2026
- **Implementation:** Versioned plan/trial/entitlement authority and test billing architecture exist; live billing does not

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
| Core       | Sales Brain, Interactions, Evidence, Revenue Brain, Methodology, Home, Actions, Accounts/People/Opportunities, Native CRM/Pipeline, Analytics, Targets, Forecast, Manager Intelligence, Ask, simple Deal Room and reviewed Closed-Won handover | Implemented internal package; public feature copy not approved |
| Growth     | Core plus Prospect and Engage | Implemented internal package |
| Complete   | Growth plus Create and supported external CRM connectors | Implemented internal package |
| Enterprise | Complete plus only individually approved scale/support/governance requirements | Custom user limit; do not claim SSO/SCIM or unbuilt features |

The authority supports contextual add-ons such as Core + Create, Core + Prospect or
Core + CRM. Here `CRM` means supported external CRM connectors; Native CRM remains
Core. Add-ons are operator-assigned and have no public price.

## Entitlement boundary

The server now derives availability from the immutable plan version, current tenant
commercial state, module entitlement, organisation policy, user permission and
provider/runtime state. A client route or price label never grants access. Feature
flags and provider state remain operational controls, not proof of purchase.

Downgrade preserves existing removed-module data as read-only/exportable and blocks
new work. It does not delete users or content. Payment-failure automation does not
exist. Trust, provenance, correction, accessibility, security and data
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

- individual add-on eligibility and prices;
- extra-user bands/prices;
- public packaging and publication copy;
- payment/billing provider, tax and legal treatment; and
- Credits economics and implementation.
