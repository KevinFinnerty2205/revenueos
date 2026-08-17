# RevenueOS Daily implementation

- **Status:** Implemented in WO-025
- **Route:** Home at `/dashboard`
- **API:** `GET /api/v1/daily`

RevenueOS Daily is the default Core Home experience. It composes current persisted
Interaction, Pre-Interaction Brief, Action Layer, Opportunity, Sales Methodology,
Revenue Brain and Next Best Action state into one bounded personal day plan. It is
application policy inside the existing modular monolith, not a new AI capability or
canonical data source.

## Request flow

The browser sends one aggregate request with its IANA timezone. The API derives the
trusted organisation and user from verified authentication, rechecks active
membership, sets transaction-local tenant context and executes bounded set-based
queries. Each optional source query uses a savepoint so a database failure can mark
only that section unavailable. Authentication, membership and tenant failures still
fail the whole request closed.

Daily reads no transcript, document body, email body, raw Evidence value, prompt or
provider payload. It does not call an AI provider or queue a job. The response carries
only small display fields, controlled reason text and existing workflow links.

## Bounds and performance

| Projection | Repository bound | Response bound |
| --- | ---: | ---: |
| Current/upcoming Interactions | 12 | 5 today plus one next reference |
| Current Actions | 50 | 5 |
| Owned open Opportunities | 100 | 3 attention items |
| Pipeline currency groups | 8 | 8 |
| Existing Next Best Actions | 12 | 3 |

Brief and intelligence readiness use grouped subqueries. Latest methodology,
Revenue Brain and Next Best Action rows use windowed/set-based queries. The query
count is constant with item count; no per-card database lookup exists. No cache or
Redis layer was added.

## Day lifecycle

“Today” is `[local midnight, next local midnight)` converted to UTC from the validated
IANA timezone. Missing timezone explicitly falls back to UTC; invalid identifiers are
rejected. The client refetches on initial load, browser focus and just after the next
browser-local midnight. It does not poll.

## Feature behaviour

- Action Layer off: Actions are not queried or shown as available.
- Revenue Brain off: change context and Next Best Action recommendations are not
  queried or shown as available.
- Sales Methodology off: methodology projections are not queried or shown as
  available.
- Other current sources remain useful when any optional source is unavailable.

The current roles both receive their own Daily. Admin settings never appear on Home,
and team aggregation remains future WO-039 work.

## Deliberate non-features

No schema migration, persisted Daily snapshot, target store, forecast, numeric deal
score, dismissal/snooze preference, add-on upsell, connector, prompt or external
provider was added. Existing source workflows remain the place to review and change
underlying state.
