# Post-partner roadmap decision

Status: **WAITING FOR MEANINGFUL PARTNER USE**. No option is preselected, and this document does not authorise implementation. WO-040 remains unauthorised.

## Decision inputs

Review Day 1, Week 1, Week 2 and Month 1 evidence; successful/failed task outcomes; preparation/administration time change; trust/correction examples; support burden; incidents; import/offboarding evidence; and the capability that users voluntarily returned to. Do not use logins/day, time in app, clicks, messages sent or calls made alone.

Before deciding, answer:

- Did the core Native CRM/Sales Brain loop solve a repeated problem?
- Did users complete it without engineering intervention?
- Did reviewed Evidence and corrections improve or damage trust?
- Did Home/Daily, Opportunity, Pipeline and Forecast reduce work done in spreadsheets/CRM?
- Was the dominant missing capability email delivery, prospect data, or neither?
- Did support/security/operations remain sustainable?
- Is the missing capability shared by the target cohort, or bespoke to one partner?

## Choose exactly one

### A. Core is valuable; narrow Gmail is the next validated need

Choose only when repeated core use is evident and users' strongest blocked workflow is moving a human-reviewed follow-up through their actual Gmail mailbox. A future separately approved work order must cover user-bound OAuth, least scopes, exact sender/recipient/content binding, idempotency, receipt/unknown-state reconciliation, reply stop, revoke/re-auth, bounce/complaint/unsubscribe, quotas and kill switch. No Campaign auto-send, tracking pixel or mailbox-wide ingestion.

### B. Core is valuable; Prospect is the stronger missing need

Choose only when core use is evident and users repeatedly cannot identify/research appropriate business Accounts/people with the current workflow. Qualify Apollo before implementation: licensing/DPA, Australian coverage and match quality, allowed fields/use, source/freshness, correction/deletion, quotas, unit economics and partner need. Do not assume Apollo or bulk enrichment is approved.

### C. Usability or trust problems dominate

Choose when users see value but cannot reliably complete, understand or trust the core loop. Fix the smallest repeated problems in navigation, onboarding, Evidence provenance/correction, data entry, Pipeline/Forecast comprehension or operational support before any live provider. Repeat affected success tasks and launch gates.

### D. Product is not delivering enough value

Choose when users do not voluntarily return for a meaningful workflow, time/work reduction is weak, or the proposition depends on broad integrations/services rather than the core. Reconsider ICP, problem, product boundary and roadmap. Do not add Gmail/Apollo simply to manufacture activity.

## Decision record

```text
Named partner and use period:
Evidence reviewed:
Core value conclusion:
Dominant missing need:
Trust/usability conclusion:
Operational/support conclusion:
Selected option A/B/C/D:
Why alternatives were rejected:
Owner decision/date:
Separate work-order required: yes
```

The next implementation starts only after the owner approves a new work order. Microsoft 365/WO-040, Gmail, Apollo, a second CRM and broader provider scope remain deferred unless this evidence explicitly justifies them.
