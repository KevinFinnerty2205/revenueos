# Microsoft Teams online-meeting assessment

**Reviewed:** 2026-08-15 against official Microsoft documentation. **Decision:**
documented production path only; no connector, OAuth grant or webhook exists.

Microsoft Graph exposes `onlineMeeting` resources and APIs for recordings,
transcripts and attendance where the meeting, policy, organiser and permissions
permit. A production path would correlate an approved Outlook/Teams event, use the
narrowest delegated or application permission supported by the exact workflow,
discover completed artefacts, and import a selected source through the shared
adapter. Application permissions and tenant-wide access may require administrator
consent; this must be proven with a design-partner tenant rather than assumed.

The assessment must also validate meeting-policy constraints, artefact ownership,
change-notification coverage, subscription renewal and where recordings reside in
Microsoft 365. RevenueOS would store only normalised IDs and imported evidence; it
would not retain Graph payloads or claim that local deletion deletes the Microsoft
original.

Primary references: [Microsoft Graph permissions
reference](https://learn.microsoft.com/en-us/graph/permissions-reference),
[list transcripts](https://learn.microsoft.com/en-us/graph/api/onlinemeeting-list-transcripts?view=graph-rest-1.0),
and [`onlineMeeting` resource](https://learn.microsoft.com/en-us/graph/api/resources/onlinemeeting?view=graph-rest-1.0).
