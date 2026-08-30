# Sales Targets experience and simplicity review

**Status:** Implemented by WO-037.

## Information architecture

Insights now uses **Overview · Targets · Funnel · Activity · Win / loss**. The tab
control wraps at narrow widths so every destination remains visible and keyboard
reachable. The global ad-hoc analytics filters disappear on Targets because target
period, owner, pipeline, currency and timezone are saved configuration rather than
temporary page filters.

Overview places a compact **Active targets** section before the analytics cards. It
shows no more than five signed-in-person and organisation goals and has no admin
controls. Administrator-only peer targets are excluded from this summary. The
dedicated Targets tab provides:

- **My targets**, including self-set and assigned goals for the signed-in person;
- **Organisation targets**, showing only shared totals;
- a configuration-only **Manage assigned targets** list, sorted by person/period,
  never progress; and
- current, past and archived views.

RevenueOS Daily has no target card or priority mutation in v1. This is deliberate:
Insights owns progress and Daily continues to answer what needs attention today.

## Creation and management

The form asks what to achieve, who it is for when the user is an administrator,
calendar period, optional Pipeline for Opportunity metrics, currency when required
and goal. Activity metrics never show or accept a Pipeline. Metrics are grouped as
outcomes, pipeline development and activity; activity cards are visually secondary
and their copy warns that more activity does not by itself establish better
performance.

Changing a current/future target opens a confirmation that names the earlier value
and explains that it remains in history. Archive also requires confirmation. Past
cards are read-only. Assigned-target owners do not see edit controls, and
administrators do not receive edit controls for another user's self-set goal.

## Progress and explanation

Cards show exact actual/goal, percentage and remaining/above-target value. Future
cards say when they start and explicitly state that no actual was invented. If the
canonical metric is unavailable, the UI says so without substituting zero.

Detail shows the metric definition/version, date semantics, owner attribution,
period scope, currency/no-FX disclosure, calculated-through date and append-only
revision history. **View this metric in Insights** preserves metric, exact date,
timezone, Pipeline and personal-owner context. No UI label uses pacing, risk,
forecast or compensation language.

## Accessibility and mobile review

Controls use semantic labels, buttons, headings, landmarks, tabs and dialogs. Exact
progress is available as text; the visual bar is an accessible `progressbar`, caps
its rendered width/ARIA maximum at 100 and still names the exact percentage above 100. Loading, empty, error, upcoming and unavailable states are explicit. Focus rings
are visible, colour is not the only signal and motion-respect classes remain in use.

The 390-pixel browser flow has no document-level horizontal overflow. Cards stack,
actions wrap and tabs wrap rather than clipping a destination. Evidence:

![Desktop Targets detail](../07-sprints/assets/wo-037-targets-desktop.png)

![Mobile Targets](../07-sprints/assets/wo-037-targets-mobile.png)

## Simplicity gate

WO-037 adds one domain, one dedicated tab and one compact Overview section. It does
not add Settings navigation, a standalone dashboard, team administration, bulk
assignment, recurring jobs, notifications, a primary-target preference, a generic
KPI builder, ranking or gamification. Those omissions are intentional.
