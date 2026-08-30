# Sales Targets security, privacy and lifecycle review

**Status:** WO-037 review complete for the implemented private-beta boundary.

## Data and threat boundary

Targets contain operational goal values, ownership and progress context. They do not
contain transcripts, prompts, customer free text, provider payloads, credentials or
compensation records. Actuals are ephemeral API calculations over already-authorised
canonical records.

Primary threats are cross-tenant attachment/IDOR, same-tenant peer inference,
privilege confusion between self-set and assigned goals, historical rewriting,
forged actuals, metric/version manipulation, currency/period abuse and sensitive
value leakage through logs/audits/exports.

## Controls

- Forced PostgreSQL RLS and composite tenant foreign keys protect both tables.
- Repositories always include organisation predicates; ordinary users additionally
  receive only organisation targets and personal targets they own. Hidden IDs return 404. Administrators may inspect tenant personal targets but cannot revise/archive
  another member's self-set target through target operations.
- Owner and pipeline IDs are resolved inside the active tenant. Organisation identity
  and timezone come from verified server context, never request authority.
- The code-owned allow-list binds metric ID/version. Extra input is forbidden and no
  request model contains actual, progress, formula, SQL or arbitrary filters.
- Goal, period, count, currency, duplicate and volume bounds fail closed.
- Target identity is immutable, revisions are append-only and past periods are
  locked. Current/future archive retains history.
- Organisation progress never exposes individual contribution. There is no peer
  comparison, rank, leaderboard, score, badge, streak, screen/click/login measure or
  target-triggered Action.

## Retention, export and deletion

Export schema version 26 includes target configuration and append-only goal revision
history. It deliberately excludes computed actual/progress because those remain
derived from canonical data and would become a misleading frozen ledger. Export is
tenant-scoped and retains no internal uniqueness or calculated cache.

Normal retention/hard deletion follows the existing private-beta organisation data
workflow. Organisation deletion cascades both target tables. Approved maintenance
may delete revisions/targets in dependency order; the runtime API cannot. Removing
or disabling a member archives their current/upcoming targets and preserves past and
revision history. Canonical source retention/deletion naturally changes later
progress because no actual copy survives.

## Logging and observability

System audit events record event type, subject ID and safe configuration metadata.
Goal values, actual values, currency amounts, customer facts and complete request or
response bodies are excluded. Operational validation monitors safe request/error
metadata and migration/readiness state; there is no attainment telemetry.

## Residual limitations

Tenant RLS is organisation-level; same-tenant personal privacy therefore also relies
on mandatory application predicates and regression tests. The current roles are only
admin/member. There is no field-level manager scope, compensation-grade immutable
actual ledger, fiscal calendar, FX or external target authority. Production launch
still depends on the repository-wide Clerk, database-role and operational gates.
