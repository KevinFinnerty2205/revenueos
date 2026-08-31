# End-to-end journey simplicity review

## Outcome

WO-039A retained the established information architecture and removed reliability
barriers rather than introducing a navigation redesign. Home remains the daily
starting point; Opportunity remains the centre of Sales Brain; Interaction remains
Prepare → Capture → Review → Follow through.

## Navigation continuity review

The desktop navigation is unchanged. The mobile four-item bar remains Today,
Interactions, Actions and Search. A semantic **More destinations** disclosure makes
Accounts, People, Pipeline, Insights, Find, Create and enabled Engage destinations
reachable without adding a fifth fixed item. Cross-module actions use canonical IDs.
Person promotion offers **Save Company first** and returns to the same Person. The
promoted Contact link opens the canonical Contact, not its edit form.

## Error, loading and recovery patterns

Primary reads announce loading. Transient GET failures receive two short bounded
retries using one request ID. Writes are attempted once. Prioritised workspaces show
**Try again** and a safe return destination; the route error boundary offers Try
again and Return Home. Safe request IDs are visible in error text. Feature gates keep
the destination discoverable while availability loads or transiently fails, then
hide only when the server authoritatively reports the feature disabled.

## Mobile journey review

At 390 px, Event Overview, People, Activity and Follow Up tabs use an equal four-column
layout and remain fully inside the viewport. Insights tabs were tested at 390 px and
the reported clipping was **NOT REPRODUCED** on the current baseline; no speculative
change was made. Long Pipeline lists render the first 100 cards and expose an
explicit next batch, avoiding a 1,000-card initial DOM. Representative Home, Search,
Interaction, Opportunity, Pipeline, Insights and Forecast screens were checked with
the fixed bottom navigation present.

## Admin/member discoverability review

Seller routes no longer expose “Unconfigured CRM mode” or similar implementation
language. Admin-only Settings and Manager controls remain capability/role gated;
members are not shown actions that the API will deny. An unavailable module uses a
customer-safe message and recovery action rather than disappearing because one
availability request failed. This does not change authorisation: the API remains the
authority and still fails closed.

## Simplicity findings

- Home now has one “Deals needing attention” heading; manager content is labelled
  “Manager review”.
- Contact and Opportunity each have one page `h1`; secondary regions are `h2`s.
- Revenue Brain's secondary header is “Account intelligence”, avoiding a duplicated
  section name.
- Ask shows the supported question families and accepts close paraphrases without
  becoming generic chat.
- The first-use guide states the canonical Account → Contact → Interaction →
  Evidence → Opportunity/Sales Brain path, and blocked preparation links back to
  onboarding.

Formal assistive-technology sessions and moderated design-partner usability remain
outside this engineering review.
