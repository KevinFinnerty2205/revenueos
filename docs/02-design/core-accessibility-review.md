# Core accessibility review

- **Review:** WO-025A, 24 August 2026
- **Standard:** existing semantic and keyboard baseline, materially reviewed rather
  than represented as a certification

## Improvements

- Desktop and mobile navigation have distinct accessible names and active-page state.
- Mobile targets have a minimum 48px layout height and content clears the fixed bar.
- Search uses a labelled native search input, submit button, status/error messages and
  semantic result groups.
- Opportunity adds a breadcrumb, stable section anchors, headings and native
  disclosure controls.
- Interaction exposes lifecycle status and a readable Prepare → Capture → Review →
  Follow through sequence.
- Feature gates now use unique IDs and section-level headings; errors use alerts while
  disabled states use status text.
- Settings exposes role and organisation in a definition list and does not render
  inaccessible admin controls for members.

## Verification boundary

Vitest covers semantics, labels, role composition and changed lifecycle behaviour.
Playwright covers keyboard-reachable visible journeys and mobile overflow. Screenshot
review covers hierarchy and clipping. This is not a claim of formal WCAG audit; screen-
reader and design-partner assistive-technology observation remains launch evidence.
