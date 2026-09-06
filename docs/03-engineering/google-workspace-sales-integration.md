# Google Workspace sales integration

**Research reviewed:** 6 September 2026 against current official Google material.  
**Implementation:** production-capable Gmail and Google Calendar adapter; disabled
and not production-active. No Google account, Workspace tenant, Cloud project, OAuth
client, paid resource, customer mailbox or customer data was used.

## Boundary and provider-neutral flow

WO-041 plugs Google Workspace into the mailbox/calendar, Engage, Action and
Interaction primitives introduced by WO-040. It does not create Gmail-specific
customer entities or a second outreach architecture.

`seller OAuth → encrypted provider-neutral connection → exact Engage review → durable
schedule → execution-time safety checks → Gmail send → provider-neutral receipt →
bounded Gmail History reconciliation`

Calendar uses the same seller connection:

`bounded primary-calendar window → incremental sync token → private-safe event
projection → conservative relationship match → explicit existing Interaction link`

The reusable records remain `IntegrationConnection`, `ProviderOutboundOperation`,
`ProviderReply`, `ProviderCalendarEvent` and `ProviderSyncState`. Provider IDs and
tokens are reconciliation inputs, never Oryntela tenant authority. Google Drive,
Docs, Sheets, Slides, Chat, Contacts, Directory, Meet calling/recording/transcription,
attachments and Calendar write are outside WO-041.

## Account and OAuth authority

Launch policy is **managed Google Workspace accounts only**. Consumer Gmail is
deferred. The OAuth request uses the confidential web-server authorisation-code flow,
PKCE S256, offline access and OIDC identity scopes. `hd=*` improves account selection
but is not trusted as enforcement: the server validates the signed ID token, exact
audience, Google issuer, expiry, nonce, verified email, stable subject and non-empty
hosted-domain (`hd`) claim.

OAuth state is random, hashed at rest, short-lived, single-use and bound to the
authenticated Oryntela organisation and user. The PKCE verifier is encrypted with
tenant/state associated data. Callback replay, forged or expired state, another
Oryntela user, redirect mismatch, missing scopes, missing offline refresh authority
and a consumer account all fail closed. Reauthorising an active connection must
return the same Google subject and Workspace domain; another account requires an
explicit disconnect first.

Only one non-revoked Microsoft 365 **or** Google Workspace primary mailbox is allowed
per organisation/user. This removes default-sender ambiguity. Switching requires
disconnect then connect; queued executions and receipts remain bound to their original
connection and provider. Historical Gmail and Microsoft provenance is never rewritten.

Access/refresh tokens are held only by the AES-256-GCM connector credential envelope.
The browser/API/export/audit surfaces omit tokens, credential references, PKCE
verifiers and sync tokens. Refresh locks the credential row and reuses a refresh made
by a concurrent worker. Permanent refresh/consent failure transitions the connection
to reauthorisation required; it does not loop.

## Exact Google scopes

The classifications below follow Google's current OAuth scope catalogues. Workspace
administrators may block an app or require explicit trust even where end-user consent
is normally available.

| Google scope | Why required | Oryntela use | Data accessed | Sensitive/restricted status | Admin/user consent | Production verification requirement |
| --- | --- | --- | --- | --- | --- | --- |
| `openid` | Bind the callback to a signed Google identity | Validate issuer, audience, nonce and stable account subject | OIDC identity claims | Non-sensitive identity | User; admin policy may restrict app access | Consent-screen configuration; verification can still be required for public branding/scopes |
| `email` | Bind the exact connected mailbox | Validate verified primary account email | Email identity claim | Non-sensitive identity | User; admin policy may restrict | Included in consent-screen/brand review as applicable |
| `profile` | Show the connected seller safely | Retain bounded display name | Basic profile name | Non-sensitive identity | User; admin policy may restrict | Included in consent-screen/brand review as applicable |
| `https://www.googleapis.com/auth/gmail.send` | Submit the seller-reviewed message | Send one plain-text message as the authenticated primary mailbox | Approved recipient, subject, body and Oryntela correlation headers | **Sensitive** | User; Workspace admin can restrict/allow apps | Sensitive-scope OAuth verification before external production use unless a documented exception applies |
| `https://www.googleapis.com/auth/gmail.readonly` | Gmail has no narrower scope that supplies strongly correlated reply bodies | Scan bounded Inbox/Sent metadata; fetch one body only after a unique Oryntela-managed match | Technically permits read-only Gmail access; actual processing is bounded headers/IDs and one matched reply body | **Restricted** | User plus possible Workspace admin app trust | Restricted-scope verification; because server-side systems transmit/store restricted data, an approved restricted-scope security assessment is expected unless Google confirms an exception |
| `https://www.googleapis.com/auth/calendar.events.readonly` | Read useful event fields without write authority | Bounded primary-calendar context and incremental event reconciliation | Read-only event time, visibility, organiser/attendees, location and safe conference URL when returned | **Sensitive** | User; Workspace admin can restrict/allow | Sensitive-scope OAuth verification before external production use unless a documented exception applies |

The **Google technical permission** granted by `gmail.readonly` is broader than
**Oryntela actual data processing**. Oryntela does not ingest a mailbox: the first
bounded scan asks for metadata only, limits itself to Inbox/Sent and a 30-day initial
lookback, persists no unrelated item, and requests `format=full` for one message only
after sender/recipient plus RFC Message-ID/reference or Gmail thread evidence yields
exactly one known outbound operation.

No Gmail modify, settings, labels, drafts, Contacts/People, Directory, Drive,
Calendar write or broad Calendar scope is requested. Offline refresh is requested by
the OAuth protocol parameter rather than a separate Google scope.

## Gmail send and durable receipt

Engage remains the authority: canonical Contact eligibility, exact approved version,
suppression, contactability, campaign state, commercial Engage write entitlement,
active membership, connection, provider feature and sender identity are rechecked by
the durable worker immediately before submission. Ordinary Google operations consume
no Oryntela Credits and use the customer's legitimate Workspace licence.

The browser cannot supply an arbitrary `From`. MIME is generated server-side as
UTF-8 plain text from bounded typed fields. `From` and `Reply-To` are the connected
mailbox. Names, addresses and subject reject CR/LF injection; Bcc and arbitrary raw
headers are absent. An Oryntela operation header plus RFC Message-ID derives from the
stable idempotency key.

Confirmation creates a queued provider-neutral operation. Claiming the worker commits
`submitting` before the Gmail call. A valid Gmail response stores message ID, thread ID
and RFC Message-ID and means **accepted for processing**, not delivered or placed in an
inbox. A definitive rejection can fail safely. A timeout, connection loss, ambiguous
write 5xx, oversized response or malformed success becomes `unknown` and is never
blindly resent. Sent-mail reconciliation requires the exact operation header, connected
sender and approved recipient before changing an unknown operation to reconciled.
This is conservative at-most-one automatic submission under ambiguity, not an
exactly-once-delivery claim.

Primary-mailbox aliases are **deferred / provider-constrained**. Google can expose
configured send-as identities through Gmail settings APIs, but safely proving them
would add the restricted `gmail.settings.basic` scope and more verification burden.
Same-domain text is not proof of Send As authority. Delegated mailboxes, Groups and
shared/delegated send-as patterns are also deferred; only the authenticated primary
mailbox is supported.

## Replies, NDRs and mailbox minimisation

Inbox and Sent are independently tracked with Gmail History cursors. The initial pass
is limited to 30 days, 50 items per page and 10 pages. Later passes request only
`messageAdded` history for the exact label. Duplicate IDs are collapsed. Expired
history IDs (404/410) reset that resource once to the same bounded lookback; an
unlimited full scan never occurs. Spam and Trash are not scanned.

An inbound message is retained only when:

- it is addressed to the connected mailbox;
- it uniquely matches a known operation using RFC `In-Reply-To`/`References` or the
  exact Gmail thread ID; and
- a normal/automatic reply is from the approved recipient, or an identifiable NDR
  carries exact RFC outbound evidence.

Subject-only correlation is prohibited. An unrelated, ambiguous or duplicate message
is discarded without a body fetch. A direct reply idempotently stops its Campaign.
Automatic replies and strong NDRs are retained with explicit kinds for review; an NDR
does not silently suppress a Contact or rewrite the provider-acceptance fact.

MIME traversal is capped at 50 parts and depth eight. Attachments, attachment IDs,
filenames and non-text parts are ignored. Inline body encodings are size-bounded;
plain text is preferred and HTML is reduced to at most 10,000 characters of inert text.
Scripts, styles, SVG, iframes and objects are discarded. No link is server-fetched and
no raw Gmail response is stored or logged.

## Google Calendar and Interaction linkage

The primary Calendar operational window is 14 days past plus 90 days future. A bounded
initial `events.list` uses `singleEvents=true` and `showDeleted=true`; subsequent calls
use Google's opaque `nextSyncToken`. It processes at most 10 pages of 50 events per
pass. Token invalidation resets once to the bounded window. Rolling the future edge
invalidates the old token and performs another bounded window sync.

Provider event ID plus connection is the stable instance key. `recurringEventId`,
`iCalUID`, etag and provider modification time support recurring instances, reschedules,
cancellations, deleted tombstones, duplicates and stale/out-of-order updates without
assuming Gmail thread semantics. Provider identities remain distinct across Microsoft
and Google, including if their raw IDs happen to collide.

For a private/confidential event, Oryntela retains only **Private event**, time,
timezone, privacy/state and the minimum provider ID/last-modified value required for
safe reconciliation. It clears attendee, organiser, location, conference URL, iCal
UID, series ID, etag and Interaction link. Event descriptions and attachments are
never requested for another workflow or persisted. An allow-listed HTTPS Google Meet
URL may be retained for a non-private event; this does not add Meet calling, recording
or transcription.

Matching considers exact existing Contact email only. Internal events remain internal;
unknown/multiple external attendees require review; no Contact, Company, Opportunity,
Interaction or Evidence is created automatically. One unambiguous active Opportunity
may provide context. A seller must explicitly link or unlink an active event to an
existing same-tenant, non-deleted Interaction. A Calendar event never proves attendance
and never becomes Evidence.

## Polling, quotas and operational health

WO-041 uses the existing durable worker with five-minute bounded incremental polling.
Gmail `watch` and Calendar `watch` were assessed but deferred because they require
Google Cloud Pub/Sub/public webhook channels, channel lifecycle/renewal, notification
verification and recovery infrastructure. Push could later wake the same token/history
reconciler; it must not become the source of truth.

At most 1,000 due organisations are discovered per pass, then the worker re-enters
forced-RLS tenant context and locks one connection. Active user and membership are
checked at discovery and execution. Reads are retried only through later bounded worker
passes. HTTP connect/read/write timeouts, a 1 MB response cap, 10-page caps and parsed
schema bounds prevent quota/retry storms. A 429 retains bounded `Retry-After` guidance;
an ambiguous write never enters the read retry path.

Safe health metadata includes connected-account state, accepted/unknown/failure count,
last successful sync, degraded category and reauthorisation requirement. Email/body,
Calendar details, OAuth material, authorisation headers, raw provider payloads and
client secrets are excluded from logs and metadata-only audits.

## Tenant security, retention and lifecycle

Migration `0057_google_workspace_sales` widens the existing provider-neutral tables,
constraints and indexes and adds no customer entity. Every row retains an explicit
organisation predicate, composite tenant relationship and forced PostgreSQL RLS. The
database enforces one primary non-revoked mailbox provider per organisation/user.

Google reply/event context follows existing organisation export, retention and
deletion policy; exports contain bounded Oryntela records, never credentials or sync
cursors. Disconnect attempts Google token revocation, always deletes the local
credential, invalidates previews, cancels queued work and stops sync/send while keeping
bounded historical records. Disabling a seller locally revokes their Google/Microsoft
mailbox and queued work. Organisation erasure makes a best-effort Google revoke call
before local cascade when valid configuration is present; local deletion is final even
if Google is unavailable.

Inbound mail and Calendar strings remain untrusted data. They can be displayed as
escaped/sanitised content but cannot issue instructions, create Evidence, mutate
canonical sales truth or acquire Action authority.

## Production activation and owner boundary

Production configuration fails closed unless exact official endpoints, HTTPS redirect,
encrypted credential key, Google client credentials, feature dependencies and a
separate explicit production-activation approval flag are present. The adapter is
production-capable but **production-active Google is NO**.

The following owner/account actions remain:

1. Kevin creates/selects the legitimate owner-controlled Google Cloud project and
   accepts any required Google terms. Codex must never request password, OTP, recovery
   code or MFA material.
2. Configure the OAuth consent screen/Google Auth Platform, verified Oryntela app
   identity, support/privacy links and exact production HTTPS redirect URI.
3. Prove ownership of the authorised domains using Google's required Search Console/
   domain process. WO-041 made no DNS change.
4. Enable only Gmail API and Google Calendar API for this project and create a
   confidential web OAuth client. Store the client secret and credential-envelope key
   in approved production secret storage.
5. Submit the sensitive/restricted scope verification evidence, least-privilege demo,
   privacy policy and data-use justification. Obtain Google's written classification
   or exception decision.
6. If required, engage a Google-approved restricted-scope security assessor and obtain
   a provider quote before commitment. **Exact assessment cost, billing frequency,
   card requirement and renewal are unknown/provider-quoted; no spend is authorised or
   incurred.** There is no code-only free substitute for a required assessment, though
   Google may confirm an applicable exception.
7. Complete provider/privacy/subprocessor/cross-border and customer Workspace admin
   review, monitoring/incident readiness, and an authorised synthetic Workspace smoke
   test covering OAuth, refresh, send, Sent, direct reply/NDR, calendar, disconnect and
   reauthorisation.
8. Only after explicit owner approval enable the provider and production-activation
   flags. Do not connect Kevin's personal account or real customer data for proof.

No external smoke test was performed: no authorised Workspace test mailbox, Cloud
project or OAuth client was supplied. Customer Workspace licensing is customer-funded.
Google API quota use and any future external assessment/Workspace cost must be reviewed
at that owner boundary before activation.

## Official research

- [OAuth 2.0 for server-side web apps](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [Gmail OAuth scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Sending email with Gmail](https://developers.google.com/workspace/gmail/api/guides/sending)
- [Gmail thread behaviour](https://developers.google.com/workspace/gmail/api/guides/threads)
- [Gmail incremental synchronisation](https://developers.google.com/workspace/gmail/api/guides/sync)
- [Gmail send-as aliases](https://developers.google.com/workspace/gmail/api/guides/alias_and_signature_settings)
- [Google Calendar OAuth scopes](https://developers.google.com/workspace/calendar/api/auth)
- [Google Calendar incremental synchronisation](https://developers.google.com/workspace/calendar/api/guides/sync)
- [Calendar events.list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)
- [Google Workspace API user-data policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
- [OAuth app verification](https://support.google.com/cloud/answer/13465431)
- [Sensitive and restricted scope requirements](https://support.google.com/cloud/answer/7454865)
- [Restricted-scope verification preparation](https://support.google.com/cloud/answer/13463817)
- [Security assessment requirements](https://support.google.com/cloud/answer/13464321)
- [Workspace API access controls](https://support.google.com/a/answer/7281227)
