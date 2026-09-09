# WO-052 — Oryntela customer-facing rebrand

- **Status:** Implementation complete; engineering review pending
- **Date:** 2026-09-09
- **Baseline:** `0fc6bdb946a0d59ac37e229791e4ea3b5e124bbd`
- **Branch:** `codex/wo-052-oryntela-customer-facing-rebrand`
- **Migration:** None
- **Feature freeze:** Preserved

## Objective

Apply the owner-approved WO-051 Oryntela identity comprehensively to the existing
customer experience while retaining stable RevenueOS technical identifiers.

## Implemented scope

- exact approved logo, wordmark, symbol, favicon and app-icon assets promoted to
  the web production asset tree;
- responsive full-lockup/symbol application in shell, product, auth, unavailable,
  public Deal Room and 404 contexts;
- Geist Sans through a framework-managed local variable WOFF2 with no runtime
  third-party request;
- approved brand tokens and accessible interaction/focus application, with
  semantic state colours retained;
- Oryntela metadata, OpenGraph defaults, favicon sizes and Apple app icon;
- customer display copy, Ask Oryntela, Oryntela CRM/Credits, connection UX, safe
  errors and support address;
- public Deal Room seller-first presentation plus restrained Oryntela attribution;
- Oryntela PPTX author metadata, safe fallback filenames, organisation-export
  download names, CRM import-template filenames and OpenAPI display metadata;
- narrow patched-version framework, test-runner and transitive overrides required
  for a zero-known-vulnerability dependency audit;
- customer-facing tests and a bounded automated legacy-brand/asset/SVG audit;
- current README, blueprint, engineering, inventory and decision documentation.

## Explicitly unchanged

No workflow, commercial policy, trial, price, Credit ledger, provider scope,
OAuth flow, Deal Room token/security boundary, Handover truth authority, RLS,
database identifier, migration, stable API route/field, production activation,
DNS, Zoho configuration or customer data changed. WO-053, WO-054, WO-055 and
WO-045 remain outside this work order.

## Validation record

The implementation handoff and draft pull request contain the exact final command
results and screenshot list. Required gates cover formatting, lint, typechecking,
285 web unit tests, 77 Playwright journeys, production web build, API formatting/
lint/typechecking, 1,272 API tests, API build, PostgreSQL zero-to-head migration,
RLS/drift proof, dependency and secret/prohibited-scope audits, generated output
checks and final brand rescan.

## Visual evidence

Twenty-seven synthetic-data screenshots cover the required desktop and 390 px
mobile surface inventory under `docs/07-sprints/assets/wo-052/`. The repository
does not contain a resolved public Deal Room token; that resolved state is verified
by the route-mocked Playwright journey, while the screenshot set records the safe
unavailable state without exposing link material.
