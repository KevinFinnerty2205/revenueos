# ADR 0075 — customer-facing Oryntela with retained RevenueOS internals

- **Status:** Accepted
- **Date:** 2026-09-09
- **Scope:** WO-052 customer-facing rebrand

## Context

WO-051 established the owner-approved Oryntela identity. The product still exposed
RevenueOS across application copy, generated-output metadata, public Deal Room
states and developer-visible API metadata. At the same time, lowercase RevenueOS
identifiers are embedded in package names, imports, database history, API contracts,
storage paths, environment settings and operational tooling.

A cosmetic full-stack rename would create migration and compatibility risk without
improving the customer experience.

## Decision

Use Oryntela on every repository-controlled customer-facing and public-developer
surface. Promote exact approved WO-051 assets into the web production asset tree,
implement the approved colour and Geist typography tokens, and update generated
output display metadata and filenames.

Retain stable technical identifiers by default, including the `revenueos` Python
package, npm package scope, database/migration names, API paths and JSON keys,
internal storage names, logger namespaces, environment variables and internal
component/class names. A customer-facing display label may change without changing
the underlying machine contract.

WO-052 introduces no database migration and does not rewrite persisted compatibility
keys. The private organisation-export path therefore remains
`revenueos-export-<id>.json`, while the HTTP download name is
`oryntela-export-<id>.json`.

## Alternatives considered

- **Rename every RevenueOS identifier:** rejected because it would require schema,
  package, route, storage and integration-contract migrations for no customer value.
- **Change copy only:** rejected because the approved logo, favicons, typography,
  colours and generated-output metadata are part of the customer experience.
- **Defer the rebrand until deployment:** rejected because WO-052 requires a
  reviewable, tested product implementation before WO-054 activation.

## Consequences

Customers experience one Oryntela identity without an unsafe technical migration.
Engineers must continue distinguishing display names from machine contracts, and
the brand regression test intentionally bans only standalone legacy display names
inside bounded web source paths. External provider-hosted branding remains a
documented WO-054 configuration boundary.
