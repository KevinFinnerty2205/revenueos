# Prospect Person mobile and simplicity review

## Review outcome

WO-027 passes the mobile simplicity gate without a navigation redesign. The existing mobile shell remains authoritative; Prospect Person pages are reached through company research.

At 390 × 844, content stays in a single column, source and trust labels wrap, contact values break safely, action buttons remain at least 44px high and there is no horizontal document overflow. The page prioritises name/role, why the person may matter, hypotheses, contact trust and Add to Sales. Research history and function explanations remain collapsible.

Keyboard and semantic review covers landmarks, heading order, labelled buttons, visible focus, native details/summary controls and confirmation-dialog focus. External links open with `noopener noreferrer` and a no-referrer policy. No images are rendered.

## Simplicity findings

- Discovery is explicit and company-scoped.
- Results are bounded and unranked.
- Unknown contact data is an honest empty state.
- Promotion is the only path to a Contact and shows duplicate review.
- Professional research stays visually separate on the Contact.

Screenshots under `docs/07-sprints/assets/wo-027-*` record desktop discovery, desktop person research, mobile person research, duplicate-safe promotion review and the promoted Contact's visibly separate public-research link.
