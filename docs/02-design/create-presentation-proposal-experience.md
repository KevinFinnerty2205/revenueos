# Create presentation and proposal experience

- **Status:** Future Create experience; not implemented
- **Question:** What should RevenueOS create for me?

## Create landing

Four primary choices are shown with recent outputs below:

- Presentation;
- Proposal;
- Business Case; and
- ROI.

The primary experience is guided. A blank prompt appears only as an optional detail
after the customer, purpose and template are established.

## Presentation flow

```text
Create presentation
Opportunity     Qantas — Network Modernisation
Purpose         Technical proposal
Audience        CIO, CISO, Head of Infrastructure
Duration        15 minutes
Sections        Situation, requirements, solution, implementation,
                ROI, case study, next steps
Template        Acme Corporate
[Review source plan]                                      [Generate]
```

The source plan separates customer-supported facts, approved corporate claims,
seller-selected assumptions and missing evidence. Generation cannot proceed with an
unapproved template or required unsupported claim.

The review shows slide thumbnails, source/claim warnings and layout overflow. Users
can regenerate one section, replace an approved content item, edit text and export
only after validation.

## Proposal flow

Choose opportunity, proposal type, template, scope, pricing inputs, timeline and
terms source. Review customer facts, assumptions and exclusions before generation.
The result is section-based, supports comments and exports DOCX/PDF after human
review. Legal/contract wording remains approved content or explicit input.

## ROI and business case

The calculation editor displays inputs, units, formula, source/owner and scenarios.
Calculated values are locked to the deterministic model. AI explanation is a
separate reviewed narrative and cannot alter numbers. Sensitivity changes show which
assumption caused the outcome.

## Template and content administration

Administrators upload, validate and approve templates; map supported layouts;
replace assets; and manage content status/effective dates. Unsupported fonts,
missing placeholders, macros/active content, overflow-prone layouts and brand
conflicts are actionable errors. Template administration is desktop-only.

## First-time, power-user, mobile and unavailable states

- First-time: select a recent Opportunity and a recommended approved template.
- Power user: duplicate a prior source plan, choose sections and pin content versions.
- Mobile: review, comment, approve and download; generation may be started from an
  Opportunity, but detailed layout editing is desktop-first.
- No Create entitlement: Opportunity Files remain accessible; one contextual learn-
  more action replaces generation controls.
- Missing evidence: produce an explicit gap checklist or omit the section; never fill
  it with plausible prose.

## Accessibility

All source and validation state is available outside thumbnails. Slide order,
headings, alt text, table semantics, colour contrast and reading order are validated
where the output format permits. Status never depends on colour alone.
