# Phone Call Intelligence guide

**Status:** Current WO-017 browser-first workflow.

Phone calls are ordinary `phone_call` Interactions. RevenueOS does not create a
second call aggregate and does not intercept a cellular or VoIP call. The user
prepares in RevenueOS, makes the call in their existing phone system and captures
the result afterwards.

## User journey

1. Create or open a phone call and explicitly select `inbound`, `outbound` or
   `unknown`. Link a Contact, company and opportunity only when they are known.
2. Scan the compact brief: Contact and role, purpose, desired next step, latest
   commitment, objection or timeline issue, recent Revenue Brain change and up to
   three recommended questions.
3. Select **Start call** to record the Interaction start time. This does not request
   microphone access or dial a number.
4. End it as **Connected**, **No answer**, **Left voicemail** or **Cancelled**.
   Elapsed time is an Interaction duration, not a carrier-certified duration.
5. For a connected call, choose AI Debrief, Voice Journal, Type Notes or an
   authorised recording import. **Finish for now** leaves capture optional.
6. Review every debrief candidate before it can update Interaction Intelligence,
   Opportunity Workspace or Revenue Brain.

Missed, voicemail and cancelled calls remain timeline events but never create
customer Interaction Intelligence. A note may describe the seller's planned
follow-up without implying that the customer responded.

## Adaptive debrief

The first phone question is **What changed?** for a known call of three minutes or
less. The whole session is capped at two questions. A normal connected call is
capped at four; Voice Journal is capped at two. A linked opportunity call lasting
at least 15 minutes may use up to five. No-answer, voicemail and cancelled calls
use one question. The existing reasoning policy can still stop earlier when the
first answer covers the material points.

Every typed or spoken debrief answer remains `salesperson_reported` and is visibly
labelled **Reported by you** after review.

## Timeline and downstream use

The Interaction list shows direction, Contact, local time, duration, outcome,
capture methods and intelligence readiness. Phone calls use the same Interaction
snapshot, Opportunity Workspace and Revenue Brain paths as other reviewed
Interactions; there is no phone-only dashboard or second Brain.

## Current limits

- no dialler, cellular interception, call-log access or phone-number enrichment;
- no native application or background microphone monitoring;
- no telephony provider integration or automatic participant matching;
- no automatic customer-direct claim promotion from a missed call; and
- production capture remains subject to private-beta, customer policy and legal
  approval.

See [Browser phone-call workflow](browser-phone-call-workflow.md),
[Imported-call recording](../03-engineering/imported-call-recording-guide.md) and
[Phone-call privacy review](../03-engineering/phone-call-security-privacy-review.md).
