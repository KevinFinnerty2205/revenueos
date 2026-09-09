# Oryntela brand implementation

**Status:** Current customer-facing implementation from WO-052

**Brand authority:** Owner-approved WO-051 identity

**Scope:** Product surfaces only; no marketing website, deployment or provider activation

## Source of truth and production assets

The owner-approved source assets remain under
`docs/00-company/assets/oryntela-brand`. They must not be edited from a production
copy. The product consumes exact copies under
`apps/web/public/brand/oryntela`:

```text
owner-approved WO-051 SVG/PNG/ICO source
  -> exact production copy in apps/web/public/brand/oryntela
  -> Next.js metadata and BrandLogo references
```

There is no proprietary generation step. Refresh a production copy with a normal
filesystem copy from the corresponding canonical file, then compare its checksum,
run the brand-surface test and run the web production build. The production folder
contains only approved final identity files; concept boards, M1–M3/S1–S2 assets,
contact sheets and review boards are documentation-only.

The shared `BrandLogo` component selects the exact primary, dark or symbol asset.
Desktop shell and product-header contexts use the full primary lockup when space
permits. Compact mobile contexts use the approved symbol. The public Deal Room
keeps the selling organisation primary and adds restrained `Powered by Oryntela`
attribution; it does not expose application navigation.

## Tokens and accessible use

`apps/web/app/globals.css` implements the approved light token map:

| Token | Value |
| --- | --- |
| `brand-primary` | `#0E1B32` Midnight |
| `brand-primary-foreground` | `#F6F4EF` Warm off-white |
| `brand-secondary` | `#204E5A` Mineral blue |
| `brand-accent` | `#C96B45` Copper |
| `brand-background` | `#F6F4EF` Warm off-white |
| `brand-surface` | `#FFFFFF` White |
| `brand-text` | `#0E1B32` Midnight |
| `brand-muted` | `#59687A` Muted slate |
| `brand-border` | `#7C8999` Border slate |
| `brand-focus` | `#C96B45` Copper |

No approved value is adjusted. Midnight carries primary controls, mineral blue
carries links and supporting interaction, and copper is limited to focus and
small non-text accents. Copper is not used for small text on light surfaces.
Existing success, warning, error and information colours remain semantically
independent. Existing multi-series chart colours and explicit labels remain
available rather than collapsing every series into the brand palette.

## Typography

The web app depends on `geist` 1.7.2 and imports `GeistSans` from
`geist/font/sans`. That package passes its variable WOFF2 through Next.js
`next/font/local`, so the framework emits a local, hashed font asset and no
runtime third-party font request occurs. The available variable range is 100–900;
product styles use the approved 400, 500, 600 and 700 weights. The fallback is
`"Geist", "Helvetica Neue", Arial, sans-serif`.

The font is licensed under SIL OFL 1.1. Canonical licence evidence remains in
`docs/00-company/assets/oryntela-brand/GEIST-OFL-1.1.txt` and
`THIRD-PARTY-LICENCES.md`; the installed package also includes its licence. One
variable WOFF2 is emitted instead of separate files per weight. Tables,
`.tabular-nums` and numeric form controls use tabular lining figures.

## Customer-facing identity boundary

Customer display copy uses `Oryntela`, with `Ask Oryntela`, `Oryntela CRM` when a
brand-qualified native CRM distinction is needed, and `Oryntela Credits` where
context needs the qualifier. Product modules remain Sales Brain, Prospect,
Engage, Create, Pipeline, Forecast, Targets, Analytics, Manager Intelligence,
Deal Room and Handover.

The following are deliberately retained for compatibility and engineering
continuity:

- Python package/import namespace `revenueos` and its console-script names;
- npm scopes/package identifiers such as `@revenueos/shared`;
- repository and filesystem paths;
- database tables, columns, functions, enum values, migrations and Alembic history;
- stable API paths, JSON fields and CRM authority values;
- environment variables, log namespaces, storage paths, cookie/session keys and
  internal DOM/component identifiers;
- internal class and module names such as `AskRevenueOS` and `RevenueOSDaily`.

Those names must not be surfaced as product copy. A future technical rename would
need a separate compatibility plan and is not part of WO-052.

## Generated outputs and external boundaries

PPTX core properties use Oryntela for author and last modifier. Customer and
selling-organisation content remains primary inside generated collateral.
Customer-facing fallback and download names use Oryntela while the private export
storage path retains `revenueos-export-*` as an internal safety contract. Public
API display metadata is `Oryntela API`; route paths are unchanged.

Repository-controlled consent and provider copy uses Oryntela without changing
OAuth scopes or execution semantics. Branding on Clerk-, Stripe-, Microsoft-,
Google-, HubSpot- or Salesforce-hosted surfaces remains an external activation
boundary for WO-054. WO-052 does not make any provider live.

## Regression strategy

`apps/web/tests/brand-surface.test.ts` prevents standalone legacy display names,
the old literal `R` placeholder and legacy teal brand utilities from returning to
customer-facing web source. It also verifies the approved production asset set and
rejects active or remote SVG content. Existing unit, browser, generated-PPTX,
Deal Room security, Handover authority, provider, billing, Credits, RLS and
migration suites provide behavioural regression coverage.
