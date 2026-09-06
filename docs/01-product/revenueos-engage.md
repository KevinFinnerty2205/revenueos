# RevenueOS Engage

> **Oryntela consolidation — 4 September 2026:** Engage remains a product
> capability, not a customer plan or a live-send claim. The
> [Oryntela master product blueprint](oryntela-master-product-blueprint.md) retains
> supervised review and provider-readiness gates.

- **Status:** WO-029 outreach, WO-030 campaigns, WO-031 Events and the inactive
  production-capable WO-040 Microsoft and WO-041 Google Workspace mailbox paths are
  implemented
- **Purpose:** Turn target accounts into conversations
- **Checkpoint 2:** Keep Engage and proceed to Create; external sending remains
  unavailable until a mailbox adapter's production activation gates are proven. See
  [Prospect and Engage readiness](prospect-engage-readiness.md).

## Product outcome

Engage uses authorised account/person research, ICP context and approved company
positioning to help a seller create relevant, respectful outreach. The user can edit
and approve messages; campaign controls prevent unbounded or deceptive automation.

## Current WO-029/WO-030 capability

- one-person personalised outreach;
- four explicit purposes and role/company-aware value messaging;
- source-backed eligible professional personalisation with **Why this message?**;
- immutable edit/re-approval and exact send review;
- separate contact-data trust, policy permission and server contactability;
- durable suppression, cooldown and daily limits; and
- visibly labelled deterministic email simulation outside production.

WO-030 adds explicit canonical-Contact Campaigns with an immutable audience/sequence
launch snapshot, one to four per-recipient source-backed steps, review-each-send and
policy-gated bounded auto-send modes, local send windows, pause/resume/stop, active
Opportunity/collision/suppression controls and seller-reported outcomes. See the
[Campaign guide](campaigns-and-sequences.md).

Production mailbox sending is not enabled. WO-040/041 add fail-closed Microsoft Graph
and Google Workspace adapters for seller-bound reviewed sends, sent-mail outcome
reconciliation, strongly correlated replies/NDRs and bounded calendar context. They do
not claim delivery, auto-detect free-text opt-outs, ingest unrelated mail, add tracking
or activate a real mailbox. See the
[WO-029 guide](personalised-outreach.md) and
[Google Workspace integration architecture](../03-engineering/google-workspace-sales-integration.md).

## Future capabilities, not implemented

- broader reply/deliverability analytics only after production evidence supports it.

## Outreach contract

Generated content may use only approved product/value context, sourced account
research, appropriate public professional person research and the campaign objective.
Unknown facts stay unknown. The system never pretends that public research is a
private relationship or invents customer evidence.

Every send-capable workflow needs:

- lawful-basis and jurisdiction policy configuration reviewed by qualified counsel;
- verified or permitted recipients;
- explicit approval policy and exact-version confirmation;
- opt-out, unsubscribe and do-not-contact suppression;
- frequency and domain reputation limits;
- time-zone-aware scheduling;
- stop on reply, opt-out, invalid recipient or account-state change;
- idempotency, provider receipt and unknown-outcome reconciliation; and
- visible connection and deliverability state.

No sequence is an autonomous spam cannon.

## Sequence model

A sequence is a versioned ordered definition such as day 1 email, day 4 follow-up,
day 9 new angle and day 16 close-out. A person's enrolment pins the approved
definition, sender, timezone and suppression state. Changes create a new version;
they do not silently rewrite already approved work.

Per-person messages remain reviewable under organisation policy. Bulk approval, if
ever allowed, is bounded to a visible recipient set and exact rendered versions.
WO-022's execution boundary is reused for live adapters; approval is not execution.

## Event workflow

WO-031 now implements this bounded manual/CSV workflow. See the
[Events guide](event-intelligence.md); event-platform connectors, registration and
ticketing remain future/out of scope.

- **Before:** ingest an authorised attendee source, identify existing Accounts and
  opportunities, rank relevant people, research and prepare invitations.
- **During:** create fast Interactions, capture business cards with permission, add a
  Voice Journal or debrief, and collect authorised Visual Evidence.
- **After:** resolve identities, summarise people met, identify opportunities,
  prepare individual follow-up and optionally create a reviewed campaign.

An attendee list is not blanket marketing consent. Authority, purpose, source and
suppression rules follow each attendee.

## Experience and packaging

Engage lives within Find for target-to-outreach flow and within an Account/Contact
context for individual outreach. Campaign management is under the existing desktop
**Sell** group and contextually linked from People, not a seventh top-level product.
The four-item mobile navigation remains unchanged; mobile supports Campaign summary,
recipient review/approve and pause/stop while authoring is desktop-oriented.

If Engage is unavailable, the seller can still copy a Core follow-up draft and act
manually. See [engagement experience](../02-design/engage-campaign-event-experience.md)
and [campaign architecture](../03-engineering/outreach-campaign-architecture.md).

## Simplicity test

- **Where/first action:** From Find, Account or Contact, choose **Create outreach**.
- **Navigation:** Campaigns is a secondary item under the existing desktop Sell group.
- **Hidden until needed:** Sequence timing, batch controls, exceptions and provider
  detail follow purpose, recipient and exact-message review.
- **Mobile:** Review, approve, pause/stop and capture event follow-up; campaign building
  is desktop-first.
- **When not purchased:** Core follow-up/copy remains available and one contextual
  explanation may be shown without repeated upsell.
- **First-time/power user:** A first-time seller sends one reviewed message; a power
  user manages bounded sequences, campaigns and exceptions.
- **AI/manual work:** deterministic sourced composition cannot choose an audience or
  approve itself; users review/launch/stop, and bounded auto-send requires explicit
  organisation and Campaign authority.
