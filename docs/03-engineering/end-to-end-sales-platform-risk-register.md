# End-to-end Sales Platform risk register

- **Status:** WO-023 planning register
- **Use:** Each future work order must re-assess relevant entries and name an owner

Ratings are qualitative planning signals, not compliance findings. `Gate` identifies
the evidence required before release; residual risk assumes the listed controls work.

## WO-031 Event controls

- Attendee overcollection/list authority: approved-field allowlist, mandatory
  versioned attestation, one-hour preview and metadata-only logging.
- False identity merge: person-specific exact email/profile only; generic inbox and
  name-only rows cannot auto-link.
- Attendance treated as consent or intent: canonical Contact/contactability remains
  mandatory; no Evidence, Methodology, Buying Signal, Revenue Brain or numeric score.
- Bulk abuse: 5 MB/500-row/50-column/five-import/50-active-Event caps, explicit
  single promotion and WO-030's 50-Contact audience cap.
- Deceptive post-Event copy: meeting language requires encounter/Interaction and
  execution reuses WO-029 suppression/source validation.

| ID  | Area             | Risk and impact                                                       | Required controls                                                       | Release gate                                  | Residual |
| --- | ---------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------- | -------- |
| R01 | Scope            | Feature accumulation obscures Sales Brain and increases learning cost | Six-area IA, one-question pages, simplicity gate, remove/defer reviews  | First-use usability evidence                  | Medium   |
| R02 | Core             | Essential Brain value is fragmented behind add-ons                    | Fixed Core contract and dependency tests                                | Core journey works with every add-on disabled | Low      |
| R03 | Tenancy          | Cross-organisation row, cache, file or job exposure                   | Explicit scope, RLS, scoped keys, fail-closed services                  | Adversarial tenant tests in PostgreSQL        | Low      |
| R04 | Identity         | Unverified/missing organisation context is accepted                   | Server-verified identity/membership; production unavailable otherwise   | Denial/configuration tests                    | Low      |
| R05 | Research         | Unlawful or prohibited-source collection                              | Provider/source review, purpose limitation, crawl/access policy         | Legal/privacy/provider approval               | Medium   |
| R06 | People           | Sensitive or protected traits are inferred or used                    | Attribute/proxy prohibitions, schema allow-list, abuse evaluation       | Red-team fixtures pass                        | Medium   |
| R07 | Research trust   | Stale, fabricated or inferred claims appear verified                  | Atomic provenance, trust states, expiry, conflicts, correction          | Source/citation quality threshold             | Medium   |
| R08 | Contacts         | Guessed business contact is treated as verified                       | Verification lifecycle/method/time; unknown by default                  | Accuracy and false-positive threshold         | Medium   |
| R09 | Consent          | Contact verification or event attendance is treated as permission     | Separate lawful-basis/consent policy and explicit enrolment             | Jurisdiction and workflow review              | Medium   |
| R10 | Outreach         | Spam or deceptive personalisation harms people and sender reputation  | Exact approval, suppression, limits, stop rules, honest personalisation | Abuse, opt-out and stop-race tests            | Medium   |
| R11 | Execution        | Retry sends a duplicate or wrong action                               | Stable idempotency, exact immutable input, receipts, reconciliation     | Fault-injection tests                         | Low      |
| R12 | Provider         | Uncertain provider result causes unsafe automatic retry               | Ambiguous state, reconciliation and manual recovery                     | Timeout/partial-failure tests                 | Medium   |
| R13 | Events           | Attendee data is imported or retained without authority               | Authority record, minimisation, retention and deletion                  | Approved event data procedure                 | Medium   |
| R14 | Recording        | Interaction capture occurs without valid consent                      | Deliberate arm, visible state, authority evidence, pause/stop           | Jurisdiction review and capture tests         | Medium   |
| R15 | AI               | Unsupported output becomes canonical fact or action                   | Schema/citation validation, proposal state, human review                | Unsupported-claim and correction thresholds   | Medium   |
| R16 | Methodology      | Projection becomes a gameable opaque qualification score              | Evidence states, explanation, no primary percentage                     | User trust/usability validation               | Low      |
| R17 | Customisation    | Custom methodology/fields become executable or corrupt the domain     | Typed bounded schema, versioning, no code/formulas                      | Boundary/limit tests                          | Low      |
| R18 | Analytics        | Ambiguous association or double counting misleads users               | Versioned population, cohort and attribution rules                      | Reconciliation against fixtures               | Medium   |
| R19 | Targets          | Activity metrics encourage surveillance or gaming                     | Outcomes-first design, no keystrokes/presence/rep score                 | Manager and seller validation                 | Low      |
| R20 | Forecast         | False precision drives poor commercial decisions                      | Range, assumptions, calibration, versions, unavailable state            | Backtest and calibration standard             | Medium   |
| R21 | Forecast bias    | Sparse or skewed history disadvantages a team/segment                 | Cohort sufficiency, bias review, simple fallback, override              | Model/rules review by segment                 | Medium   |
| R22 | Coaching         | Association is phrased as causation or performance judgement          | Evidence language, sample disclosure, prohibited metrics                | Copy and data-source audit                    | Medium   |
| R23 | Manager access   | Managers see private or irrelevant seller/customer data               | Team scope, field policy, least privilege, audit                        | Role-matrix security tests                    | Low      |
| R24 | Templates        | Malicious PPTX/DOCX exploits parser or embeds active content          | Signature/scan/isolation/resource bounds; reject active content         | Hostile-file security suite                   | Medium   |
| R25 | Generated assets | Customer facts, price or ROI are invented                             | Source classes, deterministic numbers, citation manifest, approval      | Fact/citation and render validation           | Medium   |
| R26 | Files            | Signed URL/object path leaks cross-tenant content                     | Private scoped paths, server authorisation, short expiry                | Object-access tenant tests                    | Low      |
| R27 | CRM import       | Bad mappings create duplicates or corrupt records                     | Dry run, typed mapping, duplicate review, idempotency/recovery          | Representative import rehearsal               | Medium   |
| R28 | CRM sync         | Authority conflict silently overwrites correct data                   | Field authority, version/conflict state, audit/reconciliation           | Bidirectional conflict tests                  | Medium   |
| R29 | Entitlements     | Client-side or stale cache grants/denies incorrect access             | Server enforcement, scoped versioned cache, grace policy                | Access/downgrade test matrix                  | Low      |
| R30 | Downgrade        | Customers lose access to or have data deleted unexpectedly            | Read/export grace, retention policy, asynchronous reviewed deletion     | Commercial/support runbook                    | Medium   |
| R31 | Integrations     | Tokens leak or scopes are excessive                                   | Secret manager, OAuth state/scope validation, revoke/rotate             | Provider security review                      | Low      |
| R32 | Availability     | Add-on/provider outage breaks Core                                    | Optional projections, circuit/fallback behaviour, last safe state       | Dependency-failure tests                      | Low      |
| R33 | Retention        | Derived data, backups or providers evade erasure                      | Data inventory, dependency-aware deletion, exception reporting          | Erasure rehearsal                             | Medium   |
| R34 | Residency        | “Data residency” claim ignores telemetry/backups/subprocessors        | Full data-flow mapping and enforceable placement                        | Independent architecture review               | Medium   |
| R35 | Handover         | Closed-Won package overshares raw Evidence or promises                | Purpose-bound schema, redaction, recipient/exact approval               | Handover privacy review                       | Medium   |
| R36 | Operations       | Silent job drift or no incident recovery undermines trust             | Safe metrics, alerts, kill switch, runbooks, backup/restore tests       | Operational readiness review                  | Medium   |
| R37 | Accessibility    | Dense Sales OS excludes keyboard, screen-reader or mobile users       | Semantic patterns, responsive tests, non-colour state                   | Automated and manual accessibility gate       | Low      |
| R38 | Vendor           | Provider cost, terms or lock-in invalidate product assumptions        | Adapter boundary, capability flags, cost/term review, fallback          | Commercial/provider checkpoint                | Medium   |
| R39 | Claims           | Product/competitor/security claims exceed evidence                    | Claims review, current-vs-future labels, source register                | Launch copy approval                          | Low      |
| R40 | Expansion        | Premature CRM/BI/files/no-code build delays validated value           | Roadmap checkpoints and explicit non-goals                              | Evidence-backed go/no-go                      | Medium   |

## Review cadence

The product, engineering, security/privacy and operational owners review this register
at every roadmap checkpoint and before a risky provider or external-effect release.
Any accepted high residual risk needs a named accountable owner, rationale, expiry
and rollback/kill plan. A green test suite does not by itself close a legal, customer
trust or product-adoption risk.
