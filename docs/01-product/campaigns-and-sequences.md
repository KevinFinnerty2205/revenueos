# Campaigns & Sequences implementation guide

- **Status:** implemented by WO-030 behind the Engage entitlement and campaign feature flag
- **Boundary:** bounded, canonical-Contact sales outreach; not marketing automation
- **Current delivery:** deterministic Mock Email simulation outside production; production sending fails closed

## Product contract

A Campaign is an organisation-owned objective, sender and immutable launch version. A
launch version pins an explicit Contact audience, one to four ordered steps, approval
mode, local send window, stop-on-active-Opportunity rule and organisation policy
version. The private-beta limit is 50 selected Contacts, five active campaigns per
owner and ten per organisation.

The builder accepts canonical Contact IDs only. There is no arbitrary address entry,
CSV audience import, purchased-list path, self-expanding segment or Target Market
auto-enrolment. Every selected Contact receives a visible eligibility code and reason
before launch. Blocked entries remain in the audience snapshot but are not enrolled.

## Approval modes

`review_each_send` is the default. The scheduler prepares the exact source-backed
Outreach Message, then waits for the sender to review, approve, preview and confirm it
through the existing Action/Execution boundary.

`approved_campaign_auto_send` requires all of the following:

1. the organisation administrator enables bounded campaign auto-send;
2. the campaign owner selects that mode;
3. launch includes a second, explicit auto-send confirmation; and
4. each due message is regenerated, stored, inspectable and revalidated immediately
   before execution.

The launch is authority for only that immutable campaign version—not blanket sender,
audience or content authority. Policy, recipient, source, mailbox or uncertain
delivery changes halt work.

## Sequence principles

- one to four ordered email steps; no nodes, branches or workflow scripting;
- step 1 starts at day zero and later steps wait one to 30 calendar days;
- later work is scheduled from the prior confirmed successful send, never the
  original campaign clock;
- a paused or unavailable worker does not release an overdue backlog burst;
- follow-up wording may refer to a prior note only when a successful send timestamp
  exists; no fabricated conversation, `Re:` prefix or implied familiarity;
- personalisation sources already used by an enrolment are remembered so later
  steps seek a different approved angle; and
- a final follow-up may appear only as the final step and uses a respectful close.

## Stop and safety principles

Suppression, current business email and trust, Contact/company/title snapshot,
membership, sender mailbox, entitlement, policy fingerprint, global cooldown, daily
quotas, active campaign collision, source currency and active Opportunity are checked
at the relevant construction and execution boundaries. Suppression and active
Opportunity stop an enrolment. Quota/cooldown defer without bursting. Material
recipient, source, policy or mailbox changes require attention.

Reply, meeting booked and not interested are manual seller-reported outcomes in
WO-030. RevenueOS does not read a mailbox or invent reply detection. Reporting an
outcome stops future steps and records provenance as `seller_reported`; it does not
create customer Evidence or mutate Methodology, Stakeholder Intelligence or Revenue
Brain.

## Operational reporting

Campaign reporting is limited to recipients, active/completed/stopped/blocked/needs
attention, messages sent/ready/failed and seller-reported replies/meetings. There is
no open tracking, click tracking, pixel, rep leaderboard, send-time optimisation or
A/B testing.

## Contact activity and Daily boundary

Each prepared step creates the ordinary Contact-scoped Outreach Message and Action,
so its persisted draft and sent simulation remain visible in the Contact's existing
Outreach history; the Campaign recipient timeline supplies the sequence and
seller-reported stop context. This is seller outbound activity, never Customer
Evidence. WO-030 keeps review and exception queues inside the Campaign workspace
rather than adding a second prioritisation system or flooding Daily with one Action
per recipient. The underlying reviewed Action contract remains available for future
grouping work.

## Known limitations

Production Gmail/Microsoft mailbox delivery and inbound reply detection remain
deferred. There is no Inbox, LinkedIn messaging, cold calling, event workflow,
multi-sender/domain rotation, warm-up/evasion tooling, autonomous SDR or generic
marketing automation. WO-031 owns any separately approved Event Intelligence work.
