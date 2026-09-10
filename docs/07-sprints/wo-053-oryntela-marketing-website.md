# WO-053 — Oryntela Marketing Website

- **Status:** Implemented; awaiting engineering review
- **Date:** 2026-09-10
- **Baseline:** `018266754bc73aaf017a533f26ede60e005e2aad`
- **Branch:** `codex/wo-053-oryntela-marketing-website`
- **Migration:** None
- **Provider/data/spend boundary:** no activation, no customer data, AUD $0

## Outcome

WO-053 replaces the narrow private-beta landing page with a polished public marketing
website inside the existing Next.js application. It sells the actual completed
Oryntela product as an **end-to-end sales platform** and **sales operating system**
for Australian B2B teams.

The final hero was selected after comparing three concise territories:

| Option                                            | Assessment                                                                                           |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Know what to do next                              | Strong, memorable Sales Brain promise, but too narrow for the full end-to-end platform               |
| Run your whole sales process in one place         | Clear and broad, but less specific and less distinctive                                              |
| **One sales system from prospect to handover**    | Selected: concrete endpoints, accurate product breadth, strong category fit and natural trial CTA    |

Supporting copy explicitly names Australian B2B teams and the real workflow:
finding accounts, preparing reviewed outreach, running deals, forecasting and clean
handover. The primary CTA is **Request trial access** and the secondary CTA is
**Explore the platform**.

## Implemented scope

- responsive Home, Platform, Pricing, Integrations, Security, Contact, Privacy and
  Terms routes plus updated 404 and existing Sign in entry;
- shared desktop/mobile navigation and legal-identity footer;
- exact Core/Growth/Complete/Enterprise AUD pricing and annual-prepayment language;
- exact 14-day Complete trial with no card, automatic charge or auto-conversion;
- launch-safe direct-email trial/demo conversion instead of fake signup or checkout;
- honest Microsoft 365, Google Workspace, HubSpot and Salesforce pre-launch status;
- Native Oryntela CRM as the integration-independent system-of-record choice;
- nine curated real-product screenshots from WO-052 synthetic evidence;
- page titles, descriptions, canonicals, OpenGraph/X metadata, local social card,
  robots, sitemap and truthful structured data;
- Clerk-independent public routes and retained Deal Room auth/noindex boundary;
- a production-safe branded 404 that bypasses identity initialisation while known
  application routes retain Clerk and protected-layout enforcement;
- deterministic pricing/trial/integration/metadata/route tests and 390 px checks; and
- website architecture, claim inventory and screenshot-provenance documentation.

## Legal result

- **Privacy: GAP.** No owner-approved public Privacy Notice exists.
- **Terms: GAP.** No owner-approved public Terms exist.
- **Contact: READY.** `hello@oryntela.com.au` and
  `support@oryntela.com.au` are approved and routing-tested.

Privacy and Terms have honest noindex shells. They are not represented as approved
legal documents and remain a launch blocker for WO-054.

## Security, privacy and product truth

No feature behaviour, database schema, API, provider, payment, Credit or auth policy
was added. Marketing routes bypass Clerk initialisation through an explicit public
allow-list while all product routes retain the verified protected layout. Public Deal
Room fragment-token handling and noindex/no-referrer headers remain unchanged.

The website adds no analytics, pixel, cookie, external script, chat widget, form
relay or remote font. The trust page names only implemented controls and explicitly
avoids SOC 2, ISO 27001, penetration-test, residency or other unsupported claims.

## Visual and accessibility result

The website uses only the owner-approved Oryntela identity, Geist Sans and the
Midnight/off-white/copper/mineral palette. Copper remains an accent. Responsive
product frames scale within the viewport at 390 px, and captions use an explicit
high-contrast tone on Midnight sections. The mobile navigation uses native disclosure
semantics, minimum 44 px targets, visible focus and the existing reduced-motion
override.

Focused Playwright checks cover all routes, headings, metadata, 390 px overflow,
mobile navigation/focus, exact pricing/trial text, integration wording, robots,
sitemap, OpenGraph and branded 404 behaviour.

## Documentation

- [Marketing website architecture and launch boundary](../03-engineering/oryntela-marketing-website.md)
- [Marketing claim inventory](../01-product/oryntela-marketing-claim-inventory.md)
- [Screenshot provenance](../03-engineering/oryntela-marketing-screenshot-provenance.md)

## Explicitly not performed

- no deployment, hosting activation, DNS, TLS or canonical-domain confirmation;
- no Clerk, Stripe, Microsoft, Google, HubSpot, Salesforce or Prospect-provider
  production activation;
- no Credit pack/pricing publication;
- no customer data;
- no Privacy/Terms invention or legal outreach;
- no analytics or tracking;
- no migration or API change;
- no spend; and
- no WO-055, WO-054 or WO-045 implementation.

## Validation

Implementation and repository-standard checks completed during development:

- TypeScript strict typecheck: pass;
- web formatting and ESLint: pass;
- full web Vitest: 311 tests pass across 75 files;
- focused marketing/route/commercial Vitest after final route hardening: 30 tests
  pass;
- focused public website Playwright: 13 tests pass; and
- full Playwright: 90 tests pass;
- web production build: pass, with the eight public pages, robots, sitemap and
  OpenGraph image statically generated;
- API Ruff format/lint, mypy, build and fresh-database migration drift: pass;
- API pytest: 1,273 passed and 10 skipped;
- repository audit: no known vulnerabilities; and
- all required production-build public routes returned 200, with the unknown route
  returning the branded 404 with status 404.

The final branch/commit/PR and GitHub CI results belong in the engineering handoff.
