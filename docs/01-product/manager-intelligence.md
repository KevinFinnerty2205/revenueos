# Manager Intelligence & Coaching

> **Oryntela consolidation — 4 September 2026:** Manager intelligence remains
> evidence-led attention and coaching, not employee scoring. See the
> [Oryntela master product blueprint](oryntela-master-product-blueprint.md) and
> [Daily future-state hypothesis](../02-design/oryntela-daily-future-state.md).

- **Status:** Implemented Core private-beta capability in WO-039
- **Primary question:** Which deals need attention, why, and what should we discuss?

## Product contract

Manager Intelligence evaluates Opportunities and observable sales conditions. It
does not evaluate people. An organisation administrator acting as the private-beta
sales leader can see a bounded deal-attention view, inspect the reason and source,
review recent deal changes, use evidence-backed discussion questions and record an
independent manager forecast perspective.

The experience is integrated into existing surfaces:

- Home extends RevenueOS Daily with at most five deals needing attention;
- Pipeline has an explicit Manager view with the existing owner and pipeline filters;
- Opportunity contains the flagship Manager review beside the existing Sales Brain;
- Insights Overview composes Actual, organisation Target, seller forecast, manager
  forecast and RevenueOS historical baseline as five separate references; and
- Forecast supports explicit manager review, immutable history and a factual
  **Different seller and manager views** filter.

There is no top-level Manager application.

## Evidence-backed deal review

Attention is a derived current read, not a stored risk record. Every reason has a
bounded type, plain-language explanation and source link. V1 can surface a passed
close date, overdue high-priority Action, typed Methodology conflict/gap/staleness,
stale or absent seller forecast, absent next Action and a controlled Revenue Brain
customer blocker. At most two Methodology gaps and five total reasons appear on a
list card. Reasons are de-duplicated and ordered by a published categorical order;
amount, owner, activity volume and historical outcome are not hidden weights.

The Opportunity review provides progressive disclosure:

1. what matters now;
2. why the condition appears; and
3. the canonical source to inspect.

It also shows current Actions, latest completed Interaction metadata, a safe and
bounded recent-change feed, and up to five discussion questions. Questions are
derived from the same reason/source objects. Methodology-supplied questions are
reused where available; no generic coaching prompt, AI provider or raw transcript is
used. Questions disappear when their source condition resolves and are not retained.

## Manager forecast perspective

The manager uses the same explicit `Commit`, `Likely`, `Possible` and `Not this
period` categories as the seller. It is a separate human judgment for the same
Opportunity and calendar period, with its own append-only history and the same
canonical context snapshot/staleness rules. It never edits or defaults from the
seller judgment. The Opportunity owner can see the manager view read-only; only an
administrator can append a manager revision.

RevenueOS always displays these references separately:

- Actual from `SalesMetricService`;
- organisation Target from the Target service;
- seller forecast;
- manager forecast; and
- the exact-stage historical baseline.

There is no blended or final forecast, manager probability, automatic manager
forecast or comparative seller/manager accuracy ranking.

## Coaching and no-surveillance policy

Coaching is a practical conversation about a deal and its evidence. RevenueOS does
not create a coaching note, competency record, employee profile, rating, score,
grade, rank or leaderboard. Manager Intelligence neither collects nor derives login,
session, page-view, click, screen-time, keystroke, calls-per-hour, email-volume,
response-speed, CRM-hygiene-speed, call-duration, talk-ratio, sentiment, filler-word,
interruption, emotion, personality or productivity measures. Existing factual
Activity filters remain outside this manager read model and are never transformed
into a people comparison.

Target shortfall does not mark a deal risky or create an Action. Personal Targets
are not returned in the organisation manager summary and are not presented as a
comparative attainment table.

## Access, lifecycle and limitations

The server derives organisation and role from verified tenant context. V1 uses the
existing `admin` role as the manager capability; it does not claim that every admin
is a line manager. Members cannot use organisation manager endpoints. Existing
Opportunity scope lets an owner see the manager forecast on their own deal, but not
the manager aggregate. The capability is Core and is controlled by the single
server-authoritative `managerIntelligence` feature flag.

Known limitations:

- no manager/direct-report hierarchy, team or territory structure;
- no persistent coaching notes/profile, comments, notifications or task automation;
- no employee score, ranking, compensation or quota-payroll function;
- no call-behaviour coaching, sentiment, AI coach or LLM summary;
- no automatic manager forecast, blended final forecast or cross-company benchmark;
- attention depends on canonical data RevenueOS can access; unavailable external CRM
  changes cannot be reviewed;
- sparse exact-stage history remains unavailable rather than falling back;
- no external CRM forecast sync or external provider call; and
- Checkpoint 3 remains required before broader beta or WO-040 ecosystem work.

See the [experience](../02-design/manager-intelligence-experience.md),
[architecture](../03-engineering/manager-intelligence-architecture.md) and
[security/privacy review](../03-engineering/manager-intelligence-security-privacy-review.md).
