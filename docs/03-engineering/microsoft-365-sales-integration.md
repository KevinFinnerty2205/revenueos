# Microsoft 365 sales integration

**Research reviewed:** 6 September 2026 against current Microsoft Learn material.
**Implementation:** production-capable Microsoft Graph adapter; disabled and not
production-active. No Microsoft account, tenant, app registration, paid Azure
resource, customer mailbox or customer data was used.

## Boundary and flow

WO-040 implements seller-bound Outlook mail and primary-calendar context behind the
existing provider-neutral integration, approved Action, Engage and Interaction
boundaries. It does not add SharePoint, OneDrive, Teams chat/calling/recording,
Microsoft Contacts, Outlook draft synchronisation, attachments, tracking pixels,
link rewriting or generic Microsoft automation.

`seller OAuth → encrypted connection → exact Engage review → server schedule →
execution-time policy checks → Graph sendMail → durable provider receipt → bounded
Sent Items/Inbox delta reconciliation`

Calendar uses the same seller connection:

`bounded calendarView delta → private-safe event projection → conservative Contact /
Account match → unambiguous Opportunity or review required → explicit existing
Interaction link`

The domain stores a provider-neutral outbound operation, relevant reply, calendar
event and sync state. Graph payloads, access tokens and delta cursors do not cross the
customer API. Graph IDs are provider references, never Oryntela tenant authority or
canonical Interaction identity.

## OAuth and connection authority

The confidential server application uses the Microsoft identity platform
authorisation-code flow with PKCE. Authorisation is restricted to the
`/organizations` authority: launch scope is work/school accounts only. Each state is
cryptographically random, hashed at rest, short-lived, single-use and bound to the
authenticated Oryntela organisation and user. The encrypted PKCE verifier is bound to
that state row. The callback validates redirect configuration plus the signed OIDC
token's issuer, audience, lifetime, nonce, tenant and account before storing anything.

One Microsoft work mailbox may be active per Oryntela user. An existing active
connection cannot be silently replaced with a different Microsoft account or tenant;
the seller must disconnect first. A later connection gets a new identity row, so
retained records from the revoked mailbox are never rebound to a replacement account.
The authenticated Graph `/me` identity supplies the sender address. The browser cannot
nominate `From`, tenant or account authority. Other connectors retain their existing
one-per-organisation uniqueness.

Tokens are stored only through the AES-GCM encrypted connector credential store.
Refresh reads are row-locked so concurrent workers do not rotate the same refresh
token independently. Authentication/consent failure marks the connection as needing
reauthorisation. Disconnect is idempotent, removes local credentials, stops new sync
and sends, cancels queued execution, invalidates previews and preserves bounded
historical Oryntela records. Disabling a member performs the same local credential
revocation for their owned connections. Microsoft does not expose a general OAuth
token-revocation endpoint for this delegated flow; a customer may additionally revoke
enterprise-app consent or sessions in Microsoft administration.

## Exact delegated scopes

All permissions are delegated. There are no application permissions or tenant-wide
mailbox grants.

| Scope                 | Why                                                                        | Oryntela use                                                                       | Data accessed                                                                                                             | Delegated/application    | Admin consent                                   | Customer explanation                                                     |
| --------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------ |
| `openid`              | Bind the callback to a signed Microsoft identity                           | Validate issuer, audience, nonce, account and tenant                               | OIDC identity claims                                                                                                      | Delegated identity scope | Normally no; tenant policy may require approval | Verify which work account is being connected                             |
| `offline_access`      | Server schedules and reconciliation outlive the browser session            | Obtain and safely rotate a refresh token                                           | Refresh authority for the granted scopes                                                                                  | Delegated identity scope | Normally no; tenant policy may require approval | Keep the connection working until it is disconnected or revoked          |
| `User.Read`           | Establish the exact connected seller and mailbox address                   | Read `/me` ID, display name, mail and user principal name                          | Minimal connected-user profile                                                                                            | Delegated                | Normally no; tenant policy may require approval | Show and verify the connected work account                               |
| `Mail.Send`           | Execute an immutable reviewed email                                        | POST `/me/sendMail` as the connected seller                                        | Approved recipient, subject and plain-text body                                                                           | Delegated                | Normally no; tenant policy may require approval | Send emails the seller reviewed and approved                             |
| `Mail.Read`           | `Mail.ReadBasic` excludes message bodies needed for relevant reply content | Reconcile Oryntela-tagged Sent Items and strongly correlated replies/NDRs in Inbox | Message/thread IDs, headers, sender/recipients and timestamps; subject and reply text only for an exact matched message   | Delegated                | Normally no; tenant policy may require approval | Identify replies to Oryntela-managed email so sales records stay current |
| `Calendars.ReadBasic` | Read useful event metadata without bodies, attachments or extensions       | Bounded primary-calendar delta and meeting context                                 | Basic event time, title, sensitivity, organiser/attendees, location and structured online-meeting metadata where returned | Delegated                | Normally no; tenant policy may require approval | Read relevant work-calendar events for meeting preparation               |

Microsoft tenant policies can require an administrator even where a delegated
permission is not administrator-consent-required by default. The callback and UI map
that to **Microsoft administrator approval required**; Oryntela does not bypass it.
`Mail.ReadWrite`, Contacts, Files, Directory, shared-mailbox and application scopes are
not requested.

The consent UI distinguishes Microsoft's broad technical `Mail.Read` grant from
Oryntela's narrower data use: bounded Inbox/Sent Items metadata is inspected for known
outbound relationships, unrelated mail is not stored, and subject/body content is
requested only for one strongly correlated reply.

## Mail send, receipt and unknown outcomes

The executor reuses the existing Engage controls: canonical Contact, suppression and
contactability, immutable approved content, commercial write entitlement, connected
mailbox, sender binding, provider availability, scheduling and cancellation are
rechecked immediately before a worker call. Normal Microsoft email/calendar work has
no Oryntela Credit operation.

Graph receives one plain-text message with exact `From` and `Reply-To`, the connected
seller as authority, `saveToSentItems: true`, and an `X-Oryntela-Operation-Id` derived
from the stable execution idempotency key. A Graph `202 Accepted` means Microsoft
accepted the request for processing; it is not a delivery or inbox-placement claim.
The reviewed subject and body are sent without transformation; existing Action
contracts bound them to 240 and 10,000 characters respectively before preview.

Microsoft `sendMail` has no request idempotency key or response message ID. Confirmation
persists a `queued` operation receipt; the worker claim commits it as `submitting`
before the provider request. A definitive pre-acceptance
rejection can fail or retry under the same operation. A timeout, connection loss,
ambiguous 5xx, oversized response or unexpected write response becomes `unknown` and
is never blindly resent. Sent Items delta looks for the operation header and validates
the connected sender plus approved recipient. Positive evidence changes the receipt
to reconciled; missing evidence leaves it unknown for safe operator resolution. This
is at-most-one automatic attempt under ambiguity, not exactly-once delivery.

## Reply and NDR reconciliation

Inbox and Sent Items are independently synchronised by folder delta for a bounded
30-day initial window, at most 50 items per page and 10 pages per pass. Stored delta
links are accepted only for the fixed Graph HTTPS origin. Cursor expiry resets the
bounded resource once. No full mailbox or historical import exists.

The folder delta `$select` is metadata-only and excludes both `subject` and `body`.
Oryntela requests the subject and body of one specific provider message only after the
metadata establishes exactly one strong Oryntela outbound-operation match. The second
response remains size-bounded and only the bounded subject plus sanitised plain text up
to 10,000 characters is retained.

An inbound item is retained only when all of these hold:

- it is addressed to the exact connected mailbox;
- it has a unique strong link to an Oryntela outbound operation through Internet
  Message-ID/References or Microsoft conversation ID; and
- a normal/automatic reply is from that operation's exact recipient, or an NDR is
  identifiable as a postmaster/mailer-daemon response with an exact outbound Internet
  Message-ID reference (conversation membership alone is insufficient for an NDR).

Unrelated mail, ambiguous matches, attachments and raw HTML are discarded. Retained
HTML is converted to bounded plain text; scripts, styles, objects, iframes, SVG and
remote images never render. A direct reply idempotently stops its Campaign with
provider provenance. Automatic replies and NDRs remain visible for review. WO-040
does not guess that every NDR is a permanent bounce and does not use unreliable AI
unsubscribe detection; existing explicit suppression remains authoritative.

## Calendar minimisation and Interaction linkage

The primary `calendarView/delta` window is 14 days past plus 90 days future. It rolls
forward in bounded daily increments, expires old provider event projections and keeps
only the complete delta link required by Microsoft. Calendar delta does not support
`$select`, `$top` or `$filter`; response size and page count are bounded instead, and
`Calendars.ReadBasic` constrains provider access. Bodies, attachments and extensions
are neither requested as additional scopes nor stored.

Private events retain only the label **Private event**, time, timezone, sensitivity,
state and the minimum provider event/modified identifiers needed for idempotent delta
updates; no subject, organiser, attendees, location, join URL, iCal UID, change key,
series-master ID or Interaction link survives. HTTPS structured online meeting URLs may
be retained for non-private context, but there is no Teams calling, capture or
transcription integration. For non-private events, change key, iCal UID,
series-master ID and provider modified time make instances, updates, cancellations,
deletions, duplicates and stale/out-of-order data safe. The event row is updated in
place.

Matching uses the exact existing Contact email of one external attendee or organiser.
It never creates a Contact, and events with multiple external addresses require
review. One active Opportunity for that Contact's Account can be linked; zero or
multiple candidates are unmatched/review-required. Same-domain events are internal.
Linking to an existing, same-tenant, non-deleted Interaction is explicit, idempotent
and explicitly removable. A later private transition removes the link. Calendar data
never creates Evidence or an Interaction automatically.

## Polling, throttling and worker safety

WO-040 deliberately uses the existing durable worker with bounded delta polling
instead of public Graph change-notification webhooks. This avoids a new public
callback, validation-token/client-state secret, subscription renewal and missed-
notification lifecycle before production infrastructure exists. Webhooks may later
wake the same idempotent reconciliation path; they must not become the source of truth.

The worker discovers at most 1,000 due organisations through a migration-owned
security-definer function, then re-enters forced RLS tenant context and locks one due
connection. Active user and membership status are required at discovery and execution.
Graph 429 responses preserve bounded `Retry-After` guidance; reads can retry through
the worker schedule, while ambiguous writes do not. Response bodies, tokens, mail,
calendar content and provider payloads are absent from logs.

## Persistence, privacy and lifecycle

Migration `0056_microsoft_365_sales` adds only four provider-neutral typed records:
outbound operation, relevant reply, calendar event and sync state. They use composite
tenant foreign keys, tenant-prefixed unique/index keys, explicit repository predicates
and forced PostgreSQL RLS. The authenticated Oryntela organisation remains authority;
Microsoft tenant/account IDs are support and reconciliation metadata only.

Reply bodies and calendar metadata are customer communication data. They are included
in authorised organisation export without OAuth credentials, delta cursors or
idempotency internals. Existing 30/90/180-day organisation retention removes old reply
content and calendar projections; deleting retained outreach removes its provider
reply/operation chain. Historical canonical Sales and explicitly linked Interactions
survive disconnect according to normal retention. Prompt-like text in mail or calendar
fields is inert data and never acquires Action, Evidence or tenant authority.

Before real customer use, the owner must obtain an appropriate privacy/legal review
for mailbox/calendar access, customer disclosure, Microsoft terms/DPA/subprocessor and
cross-border position, retention promises and administrator-authorisation workflow.
Repository documentation is not legal approval.

## Production activation runbook and owner boundary

Production remains fail-closed until all of the following are separately completed
and approved:

1. Kevin creates or selects the legitimate Microsoft Entra tenant/account and accepts
   any required Microsoft terms; Codex must not request a password, OTP or MFA secret.
2. Register a multi-tenant confidential web application for work/school accounts and
   record the production client ID.
3. Configure exact production HTTPS redirect URI(s); no wildcard or open redirect.
4. Add only the delegated scopes in the table and prepare the tenant-admin approval
   path. Do not grant application permissions.
5. Verify the publisher domain and complete Microsoft publisher verification if
   required for customer trust/consent UX.
6. Prefer a rotated certificate or managed secret in production secret storage;
   a client secret remains supported for development and must never enter source.
7. Approve Microsoft/provider/privacy/subprocessor and operational monitoring
   evidence, then configure the client credential and master encryption key.
8. Run an authorised synthetic smoke test for OAuth, send, Sent Items, reply, calendar,
   refresh, revocation and reauthorisation. Record the tenant/account and evidence; do
   not use real customer content.
9. Only after explicit owner activation set both the Microsoft feature flag and the
   production-activation approval gate.

No external smoke test was performed because no authorised Microsoft work account or
Entra app registration was supplied. That is an owner/account boundary, not a code
failure. Customer mailbox/Exchange licensing is customer-provided. No Oryntela-funded
licence or Azure resource is required by the implemented architecture; any future
Microsoft charge or auto-renew commitment needs separate approval.

## Official research

- [Authorisation code flow with PKCE](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Send mail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)
- [Message delta](https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0)
- [Calendar event delta](https://learn.microsoft.com/en-us/graph/api/event-delta?view=graph-rest-1.0)
- [Change-notification webhooks](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks)
- [Lifecycle notifications](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events)
- [Throttling guidance](https://learn.microsoft.com/en-us/graph/best-practices-concept)
- [User and administrator consent](https://learn.microsoft.com/en-us/entra/identity-platform/consent-types-developer)
- [Publisher-domain configuration](https://learn.microsoft.com/en-us/entra/identity-platform/howto-configure-publisher-domain)
- [Send from another user/shared mailbox](https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user)

## Deferred sender identities

- **Aliases: provider-constrained/deferred.** Oryntela exposes only the authenticated
  `/me` address. Microsoft alias presence does not prove Send As authority.
- **Shared mailbox: deferred.** Safe support requires explicit mailbox selection,
  proven Exchange delegation and `Mail.Send.Shared` (plus carefully bounded read
  authority for reconciliation). Those permissions and administration materially
  widen WO-040.

Outlook drafts, attachments and consumer Outlook.com accounts are also deferred.
