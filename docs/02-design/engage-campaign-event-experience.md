# Engage, campaign and event experience

- **Status:** Future Engage experience; not implemented
- **Question:** How do I turn this target into a conversation?

## Individual outreach

From a person or Account, **Create outreach** opens a guided review:

1. outcome and channel;
2. relevant sourced context;
3. approved value proposition;
4. generated subject/body with unsupported facts blocked;
5. recipient, sender, opt-out and suppression checks;
6. edit and exact preview; and
7. approval, schedule and provider confirmation when a live adapter exists.

The interface shows why a personalisation was used. Removing a research finding
regenerates the draft; it does not leave hidden text behind.

## Campaign workspace

The default view has four stages: **Audience → Messages → Schedule → Review**. The
user always sees total recipients, excluded/suppressed recipients, approval state and
stop conditions. Advanced delivery, experiment and provider settings are disclosed
only when needed.

A sequence step card contains delay/local send window, objective, editable template,
personalisation preview and stop behaviour. One person's rendered content can be
inspected before any bulk approval.

## Safety controls

- do-not-contact and unsubscribe are organisation-wide hard stops;
- frequency caps operate across campaigns;
- invalid/unknown recipient is excluded;
- reply, opportunity creation, opt-out or account disqualification stops later steps;
- no hidden send after content, audience or sender changes;
- deliverability and provider limits fail closed;
- send status distinguishes queued, provider accepted, delivered where known,
  bounced, replied, opted out and unknown;
- jurisdiction policy and legal review are deployment inputs, not generic legal
  conclusions in UI.

## Event experience

### Before

Upload or connect an authorised attendee source, state the permitted purpose, match
existing Accounts/Contacts, shortlist targets and prepare individual invitations.

### During

Mobile prioritises person search, quick Interaction, authorised business-card image,
Voice Journal, Debrief and Visual Evidence. It works without forcing a campaign form.

### After

RevenueOS groups people met, unresolved identity, follow-up needed and possible
opportunity. Individual review comes before any group campaign. Attendee-list access
never implies marketing consent.

## Empty and error states

- No verified recipients: explain verification and allow draft-only export.
- Suppressed audience: show counts and reasons without revealing restricted data.
- Provider unavailable: retain exact approved drafts and do not report them sent.
- Unknown outcome: stop automatic retries and provide a reconciliation state.
- Engage unavailable: Core Actions and copyable drafts remain available.

## First-time, power-user and mobile

- First-time: create one-person outreach, not a campaign.
- Power user: reusable sequences, audience rules and controlled bulk review.
- Mobile: review/approve/pause and event capture; sequence/campaign construction is
  desktop-first.

Success is measured by legitimate conversations, opt-out safety, corrections and
opportunity creation—not send volume.
