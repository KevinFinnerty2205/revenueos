# Event encounters, Interactions, outreach and Campaigns

## Encounter versus Interaction

`EventEncounter` is the low-friction seller report that a user met, wants follow-up
or completed follow-up for an EventAttendee. Its optional 1,000-character note has
origin `seller_reported_activity`. Mark-met changes per-user Event state only; it does
not write Evidence or invoke intelligence.

On deliberate capture, the service creates one Event-linked Interaction and the web
opens the existing face-to-face Companion for a planned capture. Debrief, Voice
Journal, recording, Visual Evidence, review and final intelligence continue to obey
their existing contracts. An Event note can supply seller context but never changes
origin class. Event deletion detaches and preserves the Interaction.

## Promotion

Unpromoted attendees can be planned or encountered. **Add to Sales** is required for
recipient workflows. Exact strong email may link an existing Contact; otherwise the
user reviews an exact-domain Company or explicitly creates a Company and Contact.
Created fields receive immutable `event_list` provenance and provider-supplied/unknown
trust. Shared mailboxes are not used to exact-match a person. No Opportunity,
Evidence, Methodology or Revenue Brain mutation occurs.

## Outreach truthfulness

Event drafts reuse WO-029 Action, version, source, policy and execution services.
Pre-Event copy may state that the authorised attendee list indicates attendance and
uses `event_attendance` provenance. Post-Event “Good meeting you” requires a recorded
met encounter or Interaction. Without one, copy explicitly avoids claiming a
conversation. Conversation detail still needs existing Interaction/seller-reported
support. Event source validation is skipped by Prospect revalidation because it is
not public research; all Contactability, suppression, cooldown and quota checks still
run. Outbound remains seller activity.

## Campaign handoff

The Event UI passes only explicitly selected canonical Contact IDs (maximum remains
50) plus Event ID and stage to the WO-030 builder. Campaign creation validates every
Contact belongs to the Event and tenant before persisting `EventCampaignLink`.
Audience snapshot, launch, approval, scheduling, suppression and send execution stay
inside WO-030. Raw attendees cannot be enrolled, and there is no select-all-500 or
automatic pre/post Event blast.
