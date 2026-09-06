# WO-040 — Microsoft 365 Sales Integration

- **Branch:** `codex/wo-040-microsoft-365-sales-integration`
- **Baseline:** `ce12036403057ed3801d6b6dad892b5a82af4a80`
- **Status:** implemented; engineering review passed
- **Migration:** `0056_microsoft_365_sales`
- **Provider:** Microsoft Graph production-capable adapter; not production-active
- **Data/spend:** deterministic synthetic fixtures and official public documentation
  only; AUD $0

## Outcome

WO-040 adds seller-bound Microsoft work-account OAuth, reviewed Outlook sending,
provider-neutral receipt/unknown-outcome reconciliation, strongly correlated reply
retention, bounded Outlook Calendar delta context and explicit existing-Interaction
linkage. It reuses Engage suppression, approval, scheduling, commercial entitlement,
action execution, tenant isolation, encrypted credential and worker primitives.

Graph `202 Accepted` is displayed as accepted for processing, never delivered. A
stable Oryntela operation header plus a durable pre-call receipt prevents automatic
duplicate sends: ambiguous writes remain unknown until Sent Items provides positive
sender/recipient evidence. Reply and calendar synchronisation is delta-based, bounded
by page/size/time windows and disabled for inactive members. Unrelated mail and event
bodies/attachments are not retained; private calendar details are redacted.

## Security, privacy and commercial boundary

Only delegated `openid offline_access User.Read Mail.Send Mail.Read
Calendars.ReadBasic` is requested. OAuth state is short-lived, one-time,
organisation/user-bound and PKCE-protected; OIDC identity, tenant, account and redirect
are verified. Tokens and PKCE verifier material use the encrypted server credential
store. New provider tables have composite tenant references, forced RLS and explicit
tenant predicates. Export includes customer-visible provider records but excludes
tokens and delta cursors; existing organisation retention removes aged reply/calendar
content.

Core governs connection/calendar use. Engage write entitlement and every existing
contactability/suppression/review rule govern email. Ordinary Microsoft operations do
not consume Oryntela Credits. Customer Microsoft 365/Exchange licensing remains
customer-provided.

## Honest activation state

The adapter is production-capable and fail-closed. Production is not active. No Entra
application was registered, no Microsoft account/mailbox was connected, no customer
data was processed, no Azure resource or paid trial was created and no external smoke
test was performed. Owner-managed Entra registration, production secret/certificate,
HTTPS redirects, publisher/admin-consent path, privacy/provider approval, monitoring,
authorised synthetic smoke evidence and explicit activation approval remain gates.

Aliases are provider-constrained/deferred and shared mailboxes are deferred because
neither identity strings nor a shared address prove Exchange Send As authority; shared
support would add `Mail.Send.Shared` and explicit delegation/reconciliation design.
Work/school accounts only are supported. WO-041 was not started.

## Verification scope

Deterministic tests cover PKCE and encrypted one-time OAuth state, forged/expired/user
rejection, administrator-approval UX, token non-disclosure, exact plain-text
send/From/Reply-To/Sent Items intent, timeout ambiguity and no blind retry, 429
handling, malformed responses, Microsoft delta request constraints, strong reply
matching/deduplication and malicious HTML removal, calendar matching/private data,
duplicate/stale event protection, migration reversal and tenant RLS inventory.
Existing execution, scheduling, cancellation, member/commercial rechecks,
suppression/contactability, Campaign and private-beta lifecycle suites remain
authoritative and run in the full validation gate.

The engineering review corrected seven WO-040 issues before merge: refresh-token
failures now preserve transient/retryable classification and a Graph-rejected access
token forces one row-locked refresh; unknown Microsoft sends cannot enter the generic
retry path; mailbox delta no longer requests subjects before strong correlation;
NDRs require an exact outbound Internet Message-ID reference rather than conversation
membership alone;
execution status and controls use Microsoft-specific accepted/unknown wording rather
than HubSpot labels; consent/focus semantics now explain the broad technical
`Mail.Read` grant and return keyboard focus after inline cancellation; and calendar
links are now explicitly removable while private events cannot be linked and private
transitions clear prior links and nonessential recurrence metadata. Regression
coverage exercises signed OIDC nonce validation, exact PKCE/redirect exchange,
production activation fail-closed behaviour, forced/concurrent refresh, strong
Sent Items reconciliation, unrelated-mail/NDR/automatic-reply boundaries, calendar
reschedule/cancellation/deletion/privacy transitions, provider-specific status copy
and disclosure focus.

## UI evidence

In-app browser validation covered Settings unconfigured, connecting/consent,
connected, administrator-approval, needs-reauthorisation, degraded and disconnect
states plus the Engage sender and calendar-linked meeting states at desktop and 390
px. The retained synthetic evidence contains no real account or customer data:

- [connected Microsoft settings](assets/wo-040/microsoft-settings-desktop.png)
- [desktop live-send review](assets/wo-040/engage-live-send-desktop.png)
- [390 px live-send review](assets/wo-040/engage-live-send-mobile.png)
- [desktop calendar context](assets/wo-040/calendar-context-desktop.png)
- [390 px calendar context](assets/wo-040/calendar-context-mobile.png)

See [Microsoft 365 sales integration](../03-engineering/microsoft-365-sales-integration.md)
for the architecture, exact scope table, production runbook and owner boundary.
