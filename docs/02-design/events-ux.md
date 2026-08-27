# Events UX

## Information architecture

Desktop Events is a secondary destination under **Sell**, after Campaigns. Attendees
never become a top-level area. The four-item mobile navigation is unchanged; Daily
shows one bounded active-Event card so a seller can reach today's workspace quickly.

First use says: “Get more from the events you attend. Plan who to meet, capture
conversations, and follow up while the context is fresh.” The single first action is
**Create Event**. Creation asks for name, type, dates, timezone and location, with an
optional goal. Event detail uses four tabs only: Overview, People, Activity and
Follow-up.

## Import and review

The import is a short upload → map → review → import progression in one panel. File
selection is deliberate; the browser sends bounded base64 content, never a file path.
The preview shows recognised/ignored fields, row issues and approved data only. The
authority checkbox is mandatory and sits beside the explicit warning that attendee
data does not imply outreach eligibility.

## Event-day mobile experience

People renders as cards with local name/company/title search, categorical priority,
plain-language reasons and visible trust/permission state. The primary **Mark met**
button has a 48-pixel minimum target. A quick note is optional and labelled as
seller-reported. **Follow up later**, **Add to Sales** and **Start Companion** are
separate deliberate actions. Responsive cards avoid a wide attendee table and
horizontal page overflow.

## Post-Event follow-up

The Follow-up tab shows encountered/planned people and a Campaign handoff. Campaign
checkboxes appear only for canonical Contacts. The handoff carries explicit Contact
IDs, Event ID and pre/post stage; the Campaign builder retains WO-030 audience review
and suppression controls. One-to-one draft copy says “Good meeting” only when a met
encounter/Interaction exists.

## Simplicity and accessibility review

- one Event list, one builder and one four-tab workspace;
- no agenda, ticket, registration, sponsor, booth or attendee-database UI;
- no numeric lead/intent score and no unexplained rank;
- loading, empty, read-only, validation, error and confirmation states are explicit;
- semantic headings, labelled inputs, tab roles, keyboard focus and reduced-motion
  loading treatment are present;
- mobile primary navigation is unchanged and Daily adds only a deterministic current
  Event card; and
- destructive deletion names the preserved canonical records before confirmation.

Known limitation: Event date/time editing is API-supported while the first UI editor
focuses on name, goal, venue, organiser, description and archive. Visual Evidence can
still be used through an Interaction; WO-031 adds no separate business-card/OCR path.
