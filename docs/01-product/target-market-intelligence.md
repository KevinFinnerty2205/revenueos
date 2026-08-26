# Target Market Intelligence

- **Status:** Current — WO-028
- **Purpose:** Help a seller find a small, explainable set of organisations worth researching

## Product boundary

A **Target Market** is the single user-facing concept for a bounded ICP and territory:
who the organisation serves, where those organisations operate, their minimum size,
preferred business characteristics and explicit exclusions. It is a discovery aid,
not a CRM territory assignment and not proof that a company intends to buy.

Administrators create, edit and archive Target Markets. Members can run discovery,
review results, save a prospect for later or mark it not relevant. Editing creates an
immutable revision; every historical discovery stays attached to the definition that
produced it.

## Explainable prioritisation

Every candidate is one of:

- **High priority:** known required criteria match and the available preferred or
  public trigger context makes it a strong research candidate;
- **Worth researching:** required criteria match, with less differentiating context;
- **Needs more information:** a required value is genuinely unknown; or
- **Excluded:** a known required criterion or explicit exclusion does not match.

There is no numeric lead score. Each label is accompanied by criterion-level reasons,
data origin and trust state. Missing values remain missing. High priority means strong
fit for research, not purchase intent, buying readiness or predicted conversion.

## Relationship and whitespace context

RevenueOS compares an exact normalised domain with existing tenant-owned Companies
and open Opportunities. Results clearly distinguish:

- new prospect;
- existing Account with no active Opportunity; and
- Account with an active Opportunity.

This comparison never creates or changes an Account, Contact, Opportunity, Evidence,
Methodology, Stakeholder, Revenue Brain or Action. Account research remains the
explicit next step and Add to Sales remains the explicit promotion boundary.

## Safety and limits

Discovery is deliberately bounded to 50 candidates per run, ten active Target Markets
per organisation, five runs per user per day and 25 per organisation per day. Fresh
results are reused unless the user chooses **Find again**. The current provider is a
deterministic synthetic adapter that makes no network request and fails closed in
production.

The feature does not provide scraping, sensitive-trait targeting, private-person
research, opaque scoring, intent claims, outreach, campaign enrolment, automatic
record creation, background monitoring, user-facing bulk export or a complete-market
census.

## Flagship journey

1. Open **Find** and create a Target Market through the four-step guided form.
2. Run **Find accounts** and review the summary and plain-language priority groups.
3. Inspect matched, missing and exclusion reasons with their data origin.
4. Check whether the company is new, an existing Account or already has an active Opportunity.
5. Save the prospect or start the existing sourced Account Research workflow.

The synthetic demo includes **[DEMO] Australian multi-site enterprises**, six
candidate accounts across high, needs-more-information and excluded states, and one
saved prospect.
