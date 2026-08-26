# WO-030 — Campaigns & Sequences

- **Branch:** `feature/epic-13-wo-030-campaigns-sequences`
- **Status:** implemented for draft PR; not merged
- **Migration:** `0039_campaign_sequences`
- **Boundary:** bounded canonical-Contact Engage campaigns; Mock Email simulation
  only outside production

## Outcome

WO-030 extends WO-029 from one reviewed message to an explicit audience and one to
four ordered per-recipient steps without becoming marketing automation. A launch
freezes the exact audience decisions, sequence, approval mode and organisation policy
authority. Each recipient receives its own source-backed Outreach/Action record.

## Delivered

- Campaign/version/sequence/audience/enrolment/step tenant models, composite tenant
  foreign keys, forced RLS and published-version database immutability;
- canonical Contact audience only, maximum 50 recipients and visible blocked reasons;
- review-each-send plus administrator-enabled, double-confirmed bounded auto-send;
- timezone/window-aware scheduling from prior confirmed success, five-minute
  recipient spacing, pause/resume/stop and no outage backlog burst;
- reuse of WO-029 deterministic personalisation with enrolment source memory and
  truthful follow-up/final-close rules;
- suppression, Contact/email/title/company, source, policy, entitlement, quota,
  cooldown, collision, sender mailbox and active-Opportunity revalidation;
- leased/idempotent scheduler integrated into the existing worker, unknown-delivery
  halt and safe claim failure handling;
- seller-reported replied/meeting/not-interested outcomes without fake mailbox
  detection or customer Evidence mutation;
- retention, export version 20, Contact deletion and organisation deletion coverage;
- synthetic paused demo Campaign and deterministic Mock Email/browser fixtures;
- Campaign list, builder, audience review, launch, monitoring, recipient review/send
  and mobile-safe controls under Sell; and
- component, Playwright, migration, worker, policy, RLS and cross-tenant tests.

No production Gmail/Microsoft connection, Inbox, real external email, paid service,
CSV/list import, dynamic audience, open/click tracking, sender/domain rotation,
marketing workflow builder, autonomous SDR or Event Intelligence was added.

## Approval and execution boundary

Review mode waits at `ready_for_review` for the sender's exact approval and execution
confirmation. Auto-send requires organisation policy plus a second immutable launch
confirmation; the due step still persists exact content and sources, records
campaign-launch approval basis and uses the existing preview/confirm/idempotent
Execution services. Production and missing sender-bound mailbox states fail closed.

## Stop/outcome boundary

Suppression and active Opportunity stop; quota/cooldown defer; material recipient,
source/policy/mailbox change needs attention; unknown provider state prevents retry
and next-step creation. Manual outcomes are `seller_reported`, cancel future steps and
do not alter Evidence, Methodology, Stakeholder Intelligence or Revenue Brain.

## Verification and screenshots

The complete local gate passes:

- API: 919 passed, 4 skipped; Ruff, strict mypy and package build pass;
- web: 49 files/181 tests and 45 Playwright journeys pass; lint, strict TypeScript,
  formatting and production build pass;
- PostgreSQL: migration `0039` upgrades, downgrades to `0038`, re-upgrades, reports
  no schema drift and passes both real-database tenant/RLS tests; and
- dependency and repository secret/prohibited-pattern audits pass. The migration
  check retains the pre-existing `recording_sessions`/`transcript_versions` cycle
  warning, and the test environment retains its upstream Starlette/httpx2 warning.

Ten synthetic-data fixtures under `images/wo-030/` cover first use, the builder,
auto-send warning, audience launch review, active/paused/completed summaries and
recipient review on desktop, plus summary and recipient review on a 390 px mobile
viewport. Visual QA found and corrected a mobile audience-table overflow; the
flagship journey now asserts that the document width stays within the viewport.

## Documentation

See the [product guide](../01-product/campaigns-and-sequences.md),
[UX guide](../02-design/campaigns-and-sequences-ux.md),
[domain architecture](../03-engineering/campaign-domain-architecture.md),
[scheduler](../03-engineering/campaign-scheduling-architecture.md),
[security review](../03-engineering/campaign-security-privacy-abuse-review.md),
[mailbox evaluation](../05-integrations/mailbox-provider-evaluation.md),
[reply decision](../05-integrations/reply-detection-decision.md) and ADRs
[0044](../08-decisions/0044-bounded-campaign-level-auto-send.md),
[0045](../08-decisions/0045-explicit-immutable-campaign-audience-snapshot.md) and
[0046](../08-decisions/0046-defer-campaign-reply-detection.md).

## Rollback

Disable the Campaign feature/Engage entitlement to stop new work, halt the worker and
cancel or reconcile any non-terminal Action Execution. Roll application and migration
back together to `0038_personalized_outreach` only with explicit acceptance that all
Campaign history is deleted. A rollback cannot unsend a provider-accepted message;
the current production path cannot send and automated paths are simulation-only.
