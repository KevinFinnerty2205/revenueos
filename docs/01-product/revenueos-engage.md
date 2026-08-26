# RevenueOS Engage

- **Status:** WO-029 one-to-one outreach implemented as an entitled add-on; campaigns/sequences remain future
- **Purpose:** Turn target accounts into conversations

## Product outcome

Engage uses authorised account/person research, ICP context and approved company
positioning to help a seller create relevant, respectful outreach. The user can edit
and approve messages; campaign controls prevent unbounded or deceptive automation.

## Current WO-029 capability

- one-person personalised outreach;
- four explicit purposes and role/company-aware value messaging;
- source-backed eligible professional personalisation with **Why this message?**;
- immutable edit/re-approval and exact send review;
- separate contact-data trust, policy permission and server contactability;
- durable suppression, cooldown and daily limits; and
- visibly labelled deterministic email simulation outside production.

Production mailbox sending is not enabled. Gmail and Microsoft Graph were evaluated
and deliberately deferred; no mailbox OAuth, unsubscribe route, bounce/reply event,
tracking or delivery claim exists. See the
[WO-029 guide](personalised-outreach.md) and
[provider evaluation](../05-integrations/mailbox-provider-evaluation.md).

## Future capabilities, not implemented

- short sequences with per-step content and personalisation;
- campaigns with review and scheduling;
- event invitation and follow-up workflows; and
- reply/outcome analytics only after a supported provider path exists.

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
context for individual outreach. Campaign management is a secondary area under Find
or Sell, not a seventh top-level product. Mobile supports review, approve, pause and
event capture; campaign authoring is desktop-first.

If Engage is unavailable, the seller can still copy a Core follow-up draft and act
manually. See [engagement experience](../02-design/engage-campaign-event-experience.md)
and [campaign architecture](../03-engineering/outreach-campaign-architecture.md).

## Simplicity test

- **Where/first action:** From Find, Account or Contact, choose **Create outreach**.
- **Navigation:** No new permanent item; campaigns are secondary under Find/Sell.
- **Hidden until needed:** Sequence timing, batch controls, exceptions and provider
  detail follow purpose, recipient and exact-message review.
- **Mobile:** Review, approve, pause/stop and capture event follow-up; campaign building
  is desktop-first.
- **When not purchased:** Core follow-up/copy remains available and one contextual
  explanation may be shown without repeated upsell.
- **First-time/power user:** A first-time seller sends one reviewed message; a power
  user manages bounded sequences, campaigns and exceptions.
- **AI/manual work:** AI drafts from sourced context but cannot approve; users edit,
  reject, correct sources and stop delivery.
