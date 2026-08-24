# WO-025A — Core Experience & Design-Partner Readiness

- **Status:** Implemented experience-hardening scope; target-environment launch
  approval remains environment-specific
- **Branch:** `feature/epic-11-wo-025a-core-experience-readiness`
- **Migration:** none; `0033_sales_methodology` remains the single head

## Delivered

- Consolidated desktop and mobile Core navigation while preserving existing routes.
- Replaced the unavailable Assistant destination with bounded account, opportunity and
  interaction search; no Ask/AI capability was added.
- Rebuilt onboarding around one first customer-conversation outcome.
- Added Opportunity summary → why → evidence hierarchy and progressive disclosure.
- Made Interaction actions depend on planned, active and completed lifecycle state.
- Rewrote Action and simulation states in ordinary customer language.
- Separated member and administrator Settings composition.
- Improved feature-unavailable/error semantics and fresh demo reliability.
- Added focused API, component, accessibility, role, mobile and Playwright coverage,
  plus deterministic screenshot review.

## Scope confirmation

No prompt, provider, AI schema, new intelligence, CRM connector, Prospect, Engage,
Create, forecast, manager, target or native-app capability was introduced. No backend
authorisation was moved into the browser. Existing consent, tenant, RLS, feature flag,
provenance, Action confirmation and private-beta boundaries remain authoritative.

## Screenshot and simplicity-gate evidence

The final screenshots were inspected as rendered pages, not accepted from automated
test status alone. That inspection found the completed Interaction view still gave
three debrief methods equal prominence. The final design now presents one **Capture
what happened** path and keeps guided, voice, visual and source-specific alternatives
behind contextual disclosure. The same hierarchy is used in mobile Companion.

| View         | Desktop evidence                                                                                                | Mobile evidence                                                                                           |
| ------------ | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Home / Daily | [Home desktop](assets/wo-025a-home-desktop.png)                                                                 | [Home mobile](assets/wo-025a-home-mobile.png)                                                             |
| Opportunity  | [Opportunity desktop](assets/wo-025a-opportunity-desktop.png)                                                   | [Opportunity mobile](assets/wo-025a-opportunity-mobile.png)                                               |
| Interaction  | [Before](assets/wo-025a-interaction-before-desktop.png) · [After](assets/wo-025a-interaction-after-desktop.png) | [Companion](assets/wo-025a-companion-mobile.png) · [Post-capture](assets/wo-025a-post-capture-mobile.png) |
| Methodology  | [Methodology desktop](assets/wo-025a-methodology-desktop.png)                                                   | Covered in the Opportunity mobile hierarchy                                                               |
| Actions      | [Actions desktop](assets/wo-025a-actions-desktop.png)                                                           | Mobile Actions remains one of four fixed Core destinations                                                |

Manual review confirmed one obvious next step, progressive disclosure for advanced
controls, customer-language labels, actionable boundaries and a four-item mobile
navigation. Full-page mobile evidence remains intentionally longer where it records
the completed capture and evidence-review path.

## Limitations

Ask remains WO-025B and production CRM sync remains WO-025C. Forecasting, Manager
Intelligence and Prospect remain later. There is no native app. Private-beta customer-
data and target-environment launch restrictions remain until their separate evidence
and approvals are complete.

See the [implementation guide](../03-engineering/core-experience-readiness-implementation.md),
[navigation/terminology guide](../02-design/core-navigation-and-terminology.md),
[first-time journey](../02-design/core-first-time-user-journey.md), [state guide](../02-design/core-ui-state-guide.md),
[mobile review](../02-design/core-mobile-usability-review.md) and [accessibility review](../02-design/core-accessibility-review.md).
