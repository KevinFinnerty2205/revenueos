# Core post-WO-025C simplicity review

- **Status:** Current design-readiness review
- **Reviewed:** 24 August 2026
- **Verdict:** **PASS for beginning WO-026**, with small non-blocking Core refinements
- **Design-partner status:** usable in a supervised, supported browser cohort after
  the separate launch gate

## Design conclusion

Core now has a clear product shape. A seller lands on one priority, moves through an
Interaction, reviews the deal consequence, approves the next action and returns to
Daily. Desktop navigation is task-grouped rather than module-heavy. Mobile reduces the
fixed navigation to Today, Interactions, Actions and Search. Evidence, methodology and
CRM detail are progressively disclosed close to the decision they explain.

The experience is not yet polished enough for unsupported self-serve scale. Accounts
versus Companies and People versus Contacts are inconsistent, Settings leaks internal
capability language, some completed-Interaction calls to action are ambiguous, and
the Opportunity page remains dense. These are bounded refinements. None requires a
new information architecture or should delay Prospect.

## Review method and limits

The review combined current product/design contracts with desktop and 390-pixel
mobile inspection using the deterministic synthetic organisation. It covered normal,
unknown, conflict, partial and error surfaces where available and checked the verified
WO-025A–025C screenshots for capture and CRM confirmation states.

This was not an observed usability study with design partners or a supported target
browser matrix. Local development fetch anomalies were not treated as production
defects; target-environment reliability and recovery remain part of the supervised
launch evidence.

## Primary journey review

| Surface                 | Primary purpose and action                         | Simplicity assessment                                                                                                                   | Decision                                    |
| ----------------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Home / Daily            | Identify the one thing that matters and open it    | Strong hierarchy: one dark top-priority card, upcoming Interactions, Actions and descriptive deal attention                             | **Pass**                                    |
| Onboarding              | Reach a first deal-led Interaction                 | Short, skippable, outcome-led sequence explains prepare, capture, review and follow-through                                             | **Pass**                                    |
| Accounts / People       | Find known relationships                           | Lists are simple, but navigation and page nouns conflict: Accounts/Companies and People/Contacts                                        | **Refine**                                  |
| Interactions            | See lifecycle and continue the next step           | Consolidated timeline exposes type, status, capture and intelligence state; a few completed cards use an unclear “Prepare brief” action | **Refine**                                  |
| Interaction preparation | Enter a conversation with objectives and questions | “Prepare → Capture → Review → Follow through” is clear; start action is prominent and no implicit recording is suggested                | **Pass**                                    |
| Companion / capture     | Deliberately capture or stay passive               | Quiet mobile-first controls, visible end action, explicit photo/marker choices and no background-listening implication                  | **Pass with supported-browser restriction** |
| Post-capture review     | Record what happened and finish                    | Main path is clear; advanced optional inputs become long when expanded                                                                  | **Pass; keep advanced fields collapsed**    |
| Opportunity             | Understand deal state and choose next action       | Clear top focus, risks, gaps and reviewed action; detailed Evidence/history remain close but the total page is long                     | **Pass with progressive disclosure**        |
| Methodology             | Understand and close qualification gaps            | Categorical trust states, three important gaps, suggested questions and source detail avoid score theatre                               | **Pass**                                    |
| Search                  | Find a known RevenueOS object                      | Clear deterministic default, explicit organisation scope and no misleading AI promise                                                   | **Pass**                                    |
| Ask                     | Ask a bounded account/deal question                | Scope is visible; supported/unknown behaviour is trustworthy. Narrow taxonomy can produce safe but limited value                        | **Pass for beta; measure usefulness**       |
| CRM review              | Understand and confirm an external change          | Exact current/new value, authority, confirmation and “approval is not execution” language create strong control                         | **Pass after target setup evidence**        |
| Settings                | Administer role, retention and integrations        | Functional, but technical “server feature flags” and “unrecognised capability” language leaks implementation detail                     | **Refine before broader self-serve**        |

## Navigation and terminology

The current information architecture passes the Core simplicity gate:

- **Home** is the default habit and not a report dashboard.
- **Sell** groups Accounts, People and Interactions.
- **Pipeline** is directly accessible without a separate analytics module.
- **Workspace** contains Search and Settings.
- Mobile fixes only Today, Interactions, Actions and Search.

Prospect should add **Find** only when entitled. It must not add a second global shell,
generic “AI” destination, dashboard stack or top-level entity for every research
concept.

The existing noun contract needs one clean-up pass:

| User concept               | Preferred user-facing noun | Current inconsistency to remove                                                               |
| -------------------------- | -------------------------- | --------------------------------------------------------------------------------------------- |
| Organisation being sold to | Account                    | Some headings/actions say Company                                                             |
| Person in a relationship   | Person                     | Some headings/actions say Contact                                                             |
| Active commercial motion   | Opportunity / deal         | Pipeline list heading currently says Opportunities; both are acceptable when context is clear |
| Customer touchpoint        | Interaction                | Legacy Meeting wording should remain only where historically or technically necessary         |
| Reviewed external change   | CRM update                 | Avoid “sync” where the action is a single confirmed write                                     |
| Product guidance           | RevenueOS                  | Use “AI” only where it explains a real model boundary or limitation                           |

Preferred action labels should describe the next outcome: **Prepare**, **Start
interaction**, **Capture what happened**, **Review next actions**, **Preview CRM
update**, **Confirm update**. Do not offer preparation as the primary action on a
completed Interaction.

## Hierarchy and progressive disclosure

### Daily

Keep the current hierarchy:

1. top priority and reason;
2. today's upcoming Interactions;
3. reviewed Actions;
4. deal attention; and
5. compact descriptive Pipeline context.

Targets, forecast, team comparison and manager alerts must not appear as empty shells
before their owning work orders.

### Opportunity

The first viewport should continue to answer:

- What is this deal?
- What needs attention?
- What should I do next?
- Why does RevenueOS believe that?

Methodology detail, Revenue Brain history, source lists, prior reports, visual
evidence, sync mappings and receipts should remain expandable. Progressive disclosure
must not hide the trust state or source required to judge the top recommendation.

### Ask

Search remains the safe default. Ask should always show:

- whether the scope is workspace, account or opportunity;
- the supported question boundary or starters;
- citations beside material claims;
- explicit unknown, conflicting, stale, unavailable and forbidden states; and
- a deep link to the underlying object/evidence.

Do not use a confident empty answer, simulated typing, conversational filler or an
open-ended prompt that implies web research. Provider synthesis may improve language
later but must not change the information architecture.

### CRM update

Preserve the two decisions:

1. approve the business action; and
2. preview and explicitly confirm the current external change.

Do not collapse these into one button. Always show linked provider/record, current and
new value, field authority, stale/conflict state and outcome/receipt. A disabled or
unavailable connector leaves the Opportunity readable.

## Mobile review

The mobile shell and Companion pass the start-Prospect gate:

- no horizontal overflow was observed at 390 pixels on the primary Daily surface;
- the fixed navigation reflects seller frequency rather than desktop parity;
- the next Interaction precedes secondary deal detail;
- Companion keeps start/end and deliberate capture controls reachable;
- the post-capture primary action is visible before advanced optional fields; and
- reduced content density does not remove source, trust or confirmation information.

Prospect mobile should support result scan, source/trust inspection and Save to Sell
review. It does not need a dense research workbench in WO-026. Bulk operations,
provider configuration and complex merge resolution can remain desktop-first if the
mobile surface provides a safe hand-off rather than a broken control.

## State contract

Every Core and future Prospect surface requires useful states:

| State                | Required behaviour                                                |
| -------------------- | ----------------------------------------------------------------- |
| Loading              | Preserve page purpose and avoid fake result cards                 |
| Empty                | Explain the value and one safe first action                       |
| Unknown              | State that reliable evidence is insufficient                      |
| Partial              | Show useful available content and name the unavailable dependency |
| Stale/conflicting    | Keep competing evidence visible and offer review/correction       |
| Disabled/unavailable | Explain policy/configuration and preserve Core read access        |
| Forbidden            | Reveal no tenant/object existence and provide a safe next step    |
| Error                | Safe message and request ID; retry only where idempotent          |
| Success              | Show what changed, by whom/when, and where to review it           |

Settings should translate capability state into product language such as “Not enabled
for this organisation”, “Setup required” or “Unavailable in this environment”. It
should not display internal capability registry fallbacks to normal users.

## Training burden

The offered Core journey should require a short orientation, not product training.
Use onboarding and contextual copy to teach only:

- RevenueOS never records implicitly;
- source/trust labels explain what is known;
- review changes accepted customer context;
- approving an Action does not execute it; and
- Ask may correctly say it lacks enough reliable evidence.

If a partner needs a taxonomy lecture, a feature map or administrator guidance to
complete the seller loop, treat it as a design defect or cohort restriction. Do not
solve it by adding tutorial overlays across every page.

## Non-blocking refinement ledger

| Priority | Refinement                                         | Acceptance signal                                                        |
| -------- | -------------------------------------------------- | ------------------------------------------------------------------------ |
| P1       | Align Accounts/Companies and People/Contacts nouns | shell, headings, empty states and actions use the agreed noun by context |
| P1       | Replace technical Settings capability text         | no normal admin sees “server feature flags” or “unrecognised capability” |
| P1       | Verify target-environment recovery copy and retry  | fetch/provider failure leaves purpose, request ID and safe next step     |
| P2       | Correct completed-Interaction primary actions      | completed records lead to capture/review/follow-through, not preparation |
| P2       | Correct small list copy such as “All statuss”      | visible UI copy passes review                                            |
| P2       | Measure Ask question fit                           | unsupported demand informs the next bounded taxonomy, not generic chat   |
| P3       | Continue reducing Opportunity scan length          | top decision remains clear; detail stays accessible and source-adjacent  |

P1 means important before broader self-serve, not a blocker to WO-026. If target
reliability testing exposes a reproducible data-loss, authorisation or unrecoverable
journey failure, that defect supersedes this classification.

## Prospect design constraints

WO-026 should preserve simplicity by making the journey:

**Find → understand why and source → inspect trust/contact state → review duplicate →
Save to Sell.**

The result card should show relevance, source/time and verification state before
decorative scoring. Save to Sell must state whether it will create, attach or propose
a merge. Research-provider configuration, raw payloads and internal job terminology
stay out of the seller journey.

## Design verdict

Core passes the simplicity and discoverability gate for beginning Prospect. Start
WO-026 without redesigning the shell. Complete the bounded terminology, Settings,
state-recovery and action-label refinements through normal Core maintenance and
validate the experience with supervised design partners in parallel.
