# Ask RevenueOS simplicity review

**Review status:** passed for WO-025B private-beta scope

## UX decision

Ask is a mode inside Search and a contextual secondary link on Opportunity and Account
work. It does not become a seventh desktop destination or a fifth mobile destination.
The visible hierarchy is question → concise answer/status → cited reasons →
uncertainty → collapsed sources → optional next step/follow-ups.

## Simplicity gate

1. One obvious next step: the labelled question field and **Ask** button.
2. Explicit scope: “About: …” appears on input and answer.
3. Search remains the default and retains its ordinary record-finding language.
4. Status is plain language: supported, partial, conflicting or not enough evidence.
5. The first answer is concise; details do not precede it.
6. Reasons are short cited points, not an unstructured transcript dump.
7. Sources are collapsed until requested.
8. Provenance is readable customer language, not RAG/provider terminology.
9. Conflict and uncertainty are visually separate from the main conclusion.
10. The UI states that public-web research and Action execution are unavailable.
11. Source links let the seller verify/correct underlying work.
12. Follow-ups preserve explicit scope but do not imply retained conversation memory.
13. Loading, unavailable, API error/retry and unknown states remain actionable.
14. Keyboard focus moves to the completed answer; controls have visible focus and
    44-pixel minimum targets.
15. Responsive layout stacks the input/action and source cards without horizontal
    overflow; no animation is required.

## Screenshot review

The final desktop state sequence and mobile Account conflict were captured and
inspected after Playwright completion:

- [Search page with Ask mode](../07-sprints/assets/wo-025b-ask-mode-desktop.png)
- [Opportunity Ask desktop](../07-sprints/assets/wo-025b-ask-opportunity-desktop.png)
- [Supported Opportunity answer](../07-sprints/assets/wo-025b-ask-opportunity-supported-desktop.png)
- [Conflicting answer](../07-sprints/assets/wo-025b-ask-conflict-desktop.png)
- [Unknown/public-web boundary](../07-sprints/assets/wo-025b-ask-unknown-desktop.png)
- [Account conflict mobile](../07-sprints/assets/wo-025b-ask-account-conflict-mobile.png)

The inspected views retain visible scope, concise status/answer, uncertainty and
progressive source disclosure across supported, partial, conflicting and unknown
states. The mobile capture has no horizontal overflow. The normal Search path remains
covered independently and no top-level navigation changed.
