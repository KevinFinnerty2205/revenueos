# Target Market experience

- **Status:** Current — WO-028
- **Entry:** Find → Target Markets

## Guided setup

The builder uses four short steps rather than exposing a query language:

1. **Who:** name, description, industries and optional organisation type.
2. **Where:** country and optional supported region.
3. **Shape:** minimum employee band, preferred business characteristics and research objective.
4. **Exclusions:** excluded industries and whether existing Accounts should be excluded.

Only criteria supported by the active provider capability contract are offered.
Sensitive targeting and contradictory include/exclude combinations return a safe,
specific validation message. Advanced controls stay behind **More filters**.

## Result hierarchy

The page leads with run state and a compact count summary. Local controls filter the
bounded result set by priority, relationship and saved state. Cards show company,
location, industry, size band, relationship state and the first reasons. Details
reveal all reasons and data origins; excluded rows are hidden by default but can be
reviewed.

The fixed explanation reads: **High priority means strong fit, not intent.** No
progress bar, percentage, stars or numeric score imply false precision.

Account and active-Opportunity links appear only when exact tenant-owned relationships
exist. **Research** uses the existing Account Research path. **Save** and **Not
relevant** affect only the current user’s prospect feedback.

## States and accessibility

- Empty Find has one primary **Create a target market** action and preserves direct
  known-company search.
- Pending/running uses a textual progress region; completed, partial and failed runs
  retain their durable state and safe recovery action.
- Controls use semantic labels, buttons, fieldsets, landmarks and visible focus.
- Layout collapses to one column on narrow screens; primary actions remain reachable
  without horizontal scrolling.
- Reduced-motion preferences are respected by the shared application styles.

Historical run buttons include the Target Market revision so a seller can understand
why older results differ. Archived Target Markets remain readable but cannot be edited
or searched again.
