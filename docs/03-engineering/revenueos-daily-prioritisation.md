# RevenueOS Daily prioritisation

- **Status:** Implemented deterministic policy
- **Principle:** One explainable next action, never a hidden score

## Top priority

The first matching rule wins:

1. Interaction currently in progress → **Open Companion**.
2. Unprepared Interaction from 15 minutes before its start through four hours ahead
   → **Prepare for meeting**.
3. Overdue high-priority current Action → **Review**, **Complete** or **Review
   execution**, according to its current review/execution state.
4. Completed Interaction without final validated Interaction Intelligence →
   **Capture what happened**.
5. Opportunity closing within 14 local days with a current blocker/gap → **Review
   opportunity**.
6. Other high-priority current Action.
7. Existing high-priority Next Best Action.
8. Next upcoming Interaction within the seven-day read window.

Repository order and UUID tie-breaks make equivalent candidates deterministic. No AI
model ranks Daily and there is no numeric priority score.

## Interaction rules

Daily includes non-cancelled, non-deleted Interactions created by the current user.
The effective time is actual start, then scheduled start, then created time. Today is
the user-supplied IANA local day; later Interactions are retained only to choose the
next upcoming item. Completed Interactions with no validated intelligence are
capture-needed. A completed brief means prepared. Cards show one current methodology
gap at most, otherwise the Opportunity, Account or safe generic context.

## Action rules

Only `proposed`, `edited` and `approved` Action proposals for Opportunities owned by
the current user are eligible. Rejected, superseded and manually completed Actions
are excluded. Ordering is overdue, due today, upcoming, no due date; then priority,
due time, generation time and stable ID. Approved never means complete. A latest
simulation can show in progress, simulated but still open, or needs review without
exposing execution internals. Counts can overlap: an item overdue since earlier today
is both overdue and due on the current local date.

## Deal attention

Only owned open Opportunities are considered. Up to two controlled reasons are shown
per deal and up to three deals are returned. Supported reason codes are:

- `overdue_action`
- `unresolved_risk`
- `methodology_gap`
- `conflicting_evidence`
- `upcoming_close_with_blocker`
- `interaction_stale`
- `next_action_pending`

The latest persisted projection matching the organisation's current methodology
selection supplies at most one non-confirmed field. Priority within that projection
is conflicting, stale, unknown, then partially supported; required fields win ties.
The latest completed opportunity Revenue Brain insight may add one material negative
controlled change. Daily never selects between contradictory claims.

An Action already visible in the Actions section suppresses the duplicate
`overdue_action` deal reason. Other same-code reasons are deduplicated. Close date plus
a blocker becomes `urgent`; overdue/risk/conflict becomes `needs_attention`; remaining
explainable exceptions are `watch`.

Stage-sensitive inactivity thresholds are conservative:

| Stage | Days without a meaningful completed customer Interaction |
| --- | ---: |
| Qualification | 30 |
| Discovery | 21 |
| Evaluation | 14 |
| Proposal | 10 |
| Negotiation | 7 |
| Procurement | 7 |
| Other | 21 |

## Pipeline and recommendations

Pipeline includes only owned open Opportunities. Valued Opportunities are summed by
currency; currencies are never combined. Unvalued counts remain explicit. “Closing
this month” is descriptive pipeline, not forecast. Closed-won, closed-lost, lost,
on-hold and other non-open records are excluded.

Recommended focus reuses up to three current persisted Next Best Action artefacts
referenced by eligible final Revenue Brain snapshots. Daily returns the validated
overall recommendation and controlled priority only; it does not create another
recommendation.
