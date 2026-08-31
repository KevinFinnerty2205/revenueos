# Create presentation and proposal experience

- **Status:** WO-032/033 presentation and Business Case experience, with WO-039B trust hardening; proposal path remains future
- **Question:** What should RevenueOS create for me?

## Create landing

The current Studio shows recent presentations and one primary **New presentation**
action. When no approved template exists, the first-use state explains that an
administrator must upload, review and approve an authorised PPTX. Future Proposal,
Business Case and ROI choices are not exposed.

## Presentation flow

```text
Create presentation
Account         Northstar Facilities
Opportunity     Secure rollout (optional)
Objective       Solution overview
Audience        Operations leadership
Template        Summit Corporate v1
Focus           Keep implementation concise (optional)
[Review slide plan]
```

The plan appears before generation and shows slide order, category, approved source
classes, required state and exact-text treatment. The seller can reorder or exclude
optional slides and add another approved slide. Generation cannot proceed with an
unapproved template, a removed required slide or more than 30 included slides.

The review is structured rather than a pixel-perfect in-app Office preview. Visible
copy states that the downloaded PowerPoint is the final file and that fonts, spacing
and layout may vary by device and PowerPoint version. The review shows
slide order, bounded editable text, source class, support/freshness, exact-text state,
and seller/inferred claim review. Users keep or remove claims, then explicitly approve
the complete version. Editing creates a new rendering cycle and invalidates approval.
Only the approved current structurally validated version can be downloaded through a
fresh one-time authorised request.

## Proposal flow — future

Choose opportunity, proposal type, template, scope, pricing inputs, timeline and
terms source. Review customer facts, assumptions and exclusions before generation.
The result is section-based, supports comments and exports DOCX/PDF after human
review. Legal/contract wording remains approved content or explicit input.

## ROI and business case — future

The calculation editor displays inputs, units, formula, source/owner and scenarios.
Calculated values are locked to the deterministic model. AI explanation is a
separate reviewed narrative and cannot alter numbers. Sensitivity changes show which
assumption caused the outcome.

## Template and content administration

Administrators upload an authorised `.pptx`, wait for durable structural processing,
then review every slide. They choose category, reuse state, customer-safety status,
modification policy, required state and exact-text state. Hidden or pricing-placeholder
slides cannot be approved; internal-only content fails approval. Published versions
are immutable. The page reports Template ready/needs attention/unsupported and
disables editable policies when standard writable placeholders are absent. Template
administration is desktop-only. See the [trust UX contract](create-trust-experience.md).

## First-time, power-user, mobile and unavailable states

- First-time: follow the admin template setup state, then choose an Account and an
  approved template.
- Power user: adjust the deterministic plan before generating.
- Mobile: review, approve and download; no fifth compact-navigation item and no
  template administration.
- No Create entitlement: Core remains accessible and Create fails closed without an
  aggressive upgrade prompt.
- Missing evidence: produce an explicit gap checklist or omit the section; never fill
  it with plausible prose.

## Accessibility

All source and validation state is available without relying on a rendered thumbnail.
Controls are keyboard reachable, labels and landmarks are semantic, focus is visible,
reduced motion is respected and status never depends on colour alone. The source PPTX
remains responsible for its authored reading order, alt text, contrast and layout;
RevenueOS does not claim to repair unsupported accessibility defects.
