# Oryntela 14-day free-trial hypothesis

- **Status:** **OWNER-APPROVED HYPOTHESIS FOR VALIDATION**
- **Consolidated:** 4 September 2026
- **Implementation:** No trial state, enforcement, billing or public signup is built

## Proposed experience

- 14 days;
- no credit card initially;
- simple signup when self-service readiness exists;
- broad enough product access to understand Oryntela's value rather than an
  artificially weakened Core;
- small complimentary allowance for explicitly metered external services;
- no automatic charge or surprise billing; and
- explicit selection and purchase of a paid plan after the trial.

The leading hypothesis is a bounded **Complete experience for 14 days**, but the
exact feature matrix and provider exposure are undecided. An internal supervised
design partnership is not the same thing as this future public trial.

## Trial end

At expiry, paid capabilities pause. The workspace and data should remain securely
retained for a reasonable conversion period, the customer chooses a plan, and access
reactivates only after explicit purchase. Do not delete everything on day 15, hold
data hostage or represent read-only behaviour as decided before the retention and
offboarding policies are approved.

The conversion-window length, read-only surface and deletion schedule remain open.

## Cost and abuse boundary

The trial must never create unlimited paid Prospect, enrichment, verification, SMS,
voice, research or generation cost. Complimentary Credits are small, visible and
non-negative. When they are exhausted, the metered operation stops while the rest of
the trial continues. There is no automatic top-up.

Controls must include organisation/person/device/payment-risk signals proportionate
to privacy, verified identity, quotas, rate limits, per-operation confirmation,
provider kill switches and explicit maximum exposure. Do not solve abuse by covert
tracking or by collecting unnecessary personal data.

## Public-trial prerequisites

| Prerequisite                                                | Current state                                         |
| ----------------------------------------------------------- | ----------------------------------------------------- |
| Self-service identity, organisation creation and onboarding | Not approved for public trial                         |
| Plan/module/trial entitlements                              | Architecture exists; commercial trial state not built |
| Billing and explicit purchase                               | Not built                                             |
| Trial expiry, retention, export and deletion                | Policy/implementation not final                       |
| Complimentary Credits and provider-cost caps                | Not built; quantities undecided                       |
| Abuse/fraud/rate-limit operations                           | Not proved for public access                          |
| Terms, privacy, tax and consumer/B2B legal review           | Required                                              |
| Production providers and support                            | Required for any advertised provider-backed use       |
| Observed supervised customer value                          | Required first                                        |

Do not publish or implement the trial before design-partner evidence validates time to
value, the broad-product hypothesis and the economic exposure. See
[pricing validation](oryntela-pricing-validation-plan.md).
