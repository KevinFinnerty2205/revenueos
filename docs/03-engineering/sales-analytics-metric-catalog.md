# Sales analytics metric catalogue

**Status:** WO-036 canonical definitions with the implemented WO-037 targetability
policy. These definitions are code-owned, versioned and deterministic; Targets
consumes the same registry rather than reimplementing a formula.

## Shared scope and time rules

- `startDate` and `endDate` are inclusive calendar dates in the supplied IANA
  `timezone`. Timestamp-backed facts use the corresponding half-open UTC interval.
- Custom ranges are bounded to five years. Invalid timezones and reversed or future
  ranges fail clearly.
- `actual_close_date` is already a seller-supplied calendar date. Won/Lost metrics use
  that date and the Opportunity's current final state; a currently reopened
  Opportunity is excluded.
- Opportunity filters use the current `owner_user_id`. Interaction metrics use the
  Interaction creator, and live Outreach uses the sender. Reassignment can therefore
  change historical Opportunity-filtered results in version 1; event-time owner
  credit remains a documented future requirement rather than guessed history.
- `pipelineId` may be omitted for Overview, Activity and Win/Loss. Funnel and stage
  duration require exactly one tenant-owned pipeline because stage identities are
  not combined across pipelines.
- Archived Opportunities and deleted Interactions are excluded.
- Counts are distinct canonical records. Rates always return numerator and
  denominator. A zero denominator is `unavailable`, not zero percent.
- Monetary observations are grouped by ISO currency. Missing values are counted as
  unvalued, never as zero. RevenueOS applies no FX conversion.

## Registry version 1

| Stable metric ID                            | Unit            | Date semantics                         | Definition                                                                                                   | Targetable                                     |
| ------------------------------------------- | --------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| `opportunities_created_count`               | count           | Opportunity `created_at` in range      | Distinct non-archived Opportunities created in scope                                                         | Yes                                            |
| `opportunities_closed_won_count`            | count           | `actual_close_date` in range           | Distinct Opportunities currently closed Won                                                                  | Yes                                            |
| `opportunities_closed_lost_count`           | count           | `actual_close_date` in range           | Distinct Opportunities currently closed Lost                                                                 | No                                             |
| `closed_win_rate`                           | percent         | `actual_close_date` in range           | Won / (Won + Lost), with open and reopened-currently-open Opportunities excluded                             | No; rate targets deferred                      |
| `median_sales_cycle_days`                   | days            | final `actual_close_date` in range     | Median local calendar days from Opportunity creation to current final close                                  | No                                             |
| `won_value`                                 | currency amount | `actual_close_date` in range           | Sum of valued current Won Opportunities for one required currency                                            | Yes                                            |
| `meetings_completed_count`                  | count           | Interaction `actual_end_at` in range   | Completed meeting/customer-session Interactions; phone and manual-only records excluded                      | Yes                                            |
| `phone_calls_completed_count`               | count           | Interaction `actual_end_at` in range   | Completed `phone_call` Interactions                                                                          | Yes, as supporting context only                |
| `calls_followed_by_meeting_rate_30d`        | percent         | call `actual_end_at` in range          | Mature, associated calls followed by a later completed meeting on the same Account or Contact within 30 days | No; rate targets deferred                      |
| `meetings_followed_by_progression_rate_30d` | percent         | meeting `actual_end_at` in range       | Mature, Opportunity-linked meetings followed by a later forward stage transition or Won within 30 days       | No; rate targets deferred                      |
| `live_outreach_sent_count`                  | count           | live execution `completed_at` in range | Provider-succeeded live email executions only; simulation is excluded                                        | No until a production mailbox path is approved |

Each registry item also exposes its description, numerator, denominator, exclusions,
supported filters, source domain and definition version through the product API.
Stable IDs do not contain the version: consumers persist both the ID and returned
definition version.

## Funnel cohort version 1

For one pipeline, include Opportunities whose first non-baseline entry into that
pipeline occurred inside the selected local-date range. Progression is measured
through the request time and is labelled **entered during the period; progression
measured through today**.

For every open stage actually entered by a cohort Opportunity:

- **Entered** counts the Opportunity once even after stage re-entry.
- **Advanced beyond** requires a later actual entry to a higher-position open stage
  in the same pipeline or a Won transition.
- **Still open without advancing** is current open state without the progression
  above.
- **Closed Lost without advancing** is current final Lost state without the
  progression above.

Skipped stages are never inferred. Regression does not erase an earlier actual
advance. A currently reopened Opportunity is not a final Win/Loss. A
`migration_baseline` event is never cohort entry; excluded baseline counts and the
earliest reliable tracking time are disclosed.

## Stage-duration version 1

Completed duration uses a transition's `previous_stage_entered_at` through
`changed_at` for the actual open stage it exits. The exit transition must occur in
the selected period. Null/negative intervals, migration baselines and the current
open interval are excluded. Re-entry creates another real completed interval. The
product reports median days and sample count, not a velocity score or synthetic
target.

## Activity follow-on version 1

The outcome window is fixed at 30 days. Only cohort activities whose complete window
has elapsed by request time enter a rate denominator. Recent activity still appears
in activity counts, but not in a partially observed rate.

Calls require a tenant-safe Account or Contact association. A later meeting matches
the same Account, or the same Contact through a canonical Meeting participant.
Meetings require an Opportunity and reliable non-baseline stage context at the
meeting time. A later event counts only when it moves to a higher-position open stage
in the same pipeline or Won. Backward movement and Lost do not count.

These are observed sequences. UI and API language uses **followed by** and never
claims the earlier activity caused, drove or received credit for the outcome.

## Win/Loss version 1

Reasons use only the controlled `outcome_reason` on current final Won/Lost
Opportunities and are labelled **seller reported**. Missing reasons appear as
Unknown. Free-text `outcome_note` is neither selected nor returned. Loss stage uses
the `from_stage` snapshot on the final Lost transition. Sales-cycle and monetary
breakdowns follow the shared definitions above and show sample counts.

## Explicit exclusions

The catalogue has no login, click, screen-time, presence, CRM-update-speed,
call-duration ranking, leaderboard, rep score, open/click tracking, probability,
weighted pipeline, forecast category, predicted close, arbitrary formula, SQL or
custom report metric. It reads canonical business records only and cannot mutate
Evidence, Methodology or Revenue Brain.
