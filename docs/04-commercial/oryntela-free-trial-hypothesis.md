# Oryntela 14-day trial

- **Status:** Commercial authority implemented by WO-047; public self-service not approved
- **Consolidated:** 4 September 2026
- **Billing:** Test-mode architecture implemented by WO-048; live billing not activated

## Implemented authority

A support operator may explicitly start one trial per organisation, including from
the unused Core provisioning baseline. The trial:

- runs for exactly 14 days from its recorded UTC start;
- grants the Complete V1 module profile;
- requires no credit card;
- never charges automatically;
- records start, end, grace end, actor, reason and immutable history; and
- uses an injected clock in boundary tests.

There is no public signup or browser control for trial dates. An organisation cannot
restart its trial after `trial_used_at` is set. A support operator may assign an
approved active plan during trial or grace.

## Trial end and grace

At the exact 14-day end instant the trial becomes a 30-day grace period. Existing
data remains visible and exportable, but new Core/module mutations and new external
actions are blocked. At the exact grace-end instant commercial access expires and
business routes fail closed. Data remains governed by normal retention, export and
approved erasure; neither transition purges it.

The admin Settings projection shows the status, dates and plain-language next step.
It does not suggest that payment, checkout or automatic conversion exists.

## Provider and cost boundary

Complete commercial inclusion does not activate a provider. Current deployment flags,
configuration and mocks remain authoritative for operational availability. Prospect
may be mock-only, Engage simulation-only and external CRM unavailable during a trial.
No complimentary Credits, paid provider allowance or automatic top-up is implemented.

## Public-trial prerequisites still open

| Prerequisite                                      | Current state                                      |
| ------------------------------------------------- | -------------------------------------------------- |
| Plan/module/trial access authority                | Implemented                                        |
| Trial expiry and 30-day read/export grace         | Implemented                                        |
| Self-service signup and abuse/fraud operations    | Not approved or implemented                        |
| Billing and explicit purchase                     | Not implemented                                    |
| Credits/provider-cost caps                        | TEST-only controls implemented; production quantities undecided |
| Terms, privacy, tax and consumer/B2B legal review | Required                                           |
| Production provider and support readiness         | Required for any advertised provider-backed value |
| Supervised customer value evidence                | Required                                           |

Do not publish or open a self-service trial without a separate owner work order and
the applicable launch, legal, privacy, support and cost controls.
