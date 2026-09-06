# WO-041 — Google Workspace Sales Integration

- **Branch:** `codex/wo-041-google-workspace-sales-integration`
- **Baseline:** `71d38384429f3dc18c1914720782957221e2c194`
- **Status:** implemented and engineering-reviewed
- **Migration:** `0057_google_workspace_sales`
- **Provider:** Gmail API plus Google Calendar API; production-capable and not
  production-active
- **Data/spend:** deterministic synthetic fixtures and official public documentation
  only; AUD $0

## Outcome

WO-041 adds managed-Workspace seller OAuth, server-bound Gmail MIME sending, durable
accepted/unknown/reconciled receipts, strongly correlated reply/automatic-reply/NDR
retention, Gmail History cursors, bounded Google Calendar sync tokens and explicit
existing-Interaction linkage. It reuses WO-040's provider-neutral records and the
existing Engage approval, suppression, scheduling, commercial entitlement, worker,
encrypted credential and tenant isolation boundaries.

The implementation requests only identity, `gmail.send`, `gmail.readonly` and
`calendar.events.owned.readonly`. The UI explains that Google's restricted read scope is
technically broader than Oryntela's bounded processing. No unrelated body, full
mailbox, attachment, event description, private-event detail, raw payload, token or
sync cursor reaches a customer surface or log. Calendar uses a partial-response field
mask so event descriptions and attachments are not returned by Google.

## Safety properties

- Workspace hosted-domain identity, signed OIDC nonce/audience/issuer, tenant/user
  state binding, PKCE, exact redirect and callback replay controls fail closed. The
  PKCE/state lifecycle is shared with Microsoft; provider identity and token rules
  remain adapter-specific.
- One Microsoft or Google primary non-revoked mailbox is allowed per seller. Provider
  switches require disconnect and cannot reroute queued sends.
- Sender is the connected primary mailbox; aliases/delegation are deferred rather
  than inferred.
- The durable worker rechecks membership, Engage entitlement, policy, Contact,
  suppression, schedule, connection and sender immediately before Gmail submission.
- Gmail acceptance is not called delivery. Ambiguous writes become unknown and are
  not resent without strong Sent evidence.
- Initial Gmail reconciliation is 30 days; Calendar is 14 days past/90 days future;
  both use 50-item, 10-page caps and provider incremental cursors.
- Reply bodies are fetched only after one strong Oryntela-operation match. MIME is
  bounded and sanitised; inbound attachments are ignored.
- Private Calendar events retain only an opaque reconciliation identity, time and safe
  private label. Calendar never creates Evidence, Contacts or Interactions.
- Forced PostgreSQL RLS, tenant predicates and tenant-prefixed constraints cover every
  widened provider row.
- Member disable, disconnect and organisation deletion remove local credential
  authority and queued work; disconnect/deletion attempt Google revocation safely.

## Deliberate decisions and deferrals

Consumer Gmail, send-as aliases, delegated/shared/Group sending, Gmail attachments,
Spam/Trash scanning, push/watch infrastructure, Google Contacts/Directory/Drive,
Calendar write and Google Meet calling/capture are deferred. Durable five-minute
incremental polling is simpler and consistent with the Microsoft path. Ordinary
Gmail/Calendar operations use no Oryntela Credits.

Production remains fail-closed. Google OAuth sensitive/restricted-scope verification,
the expected restricted-scope security assessment (unless Google confirms an
exception), domain/app verification, owner-created Cloud project/OAuth client,
customer/admin/privacy review, production secrets, monitoring and a synthetic
Workspace smoke test are external pre-production gates. No verification, account,
project, DNS, paid resource or commercial commitment was created.

## Evidence and handoff

The deterministic suite uses no Google account, credential, network or quota. It
covers OAuth/PKCE/nonce/replay/account replacement, encrypted secret storage,
provider switching, production fail-closed configuration, MIME/header safety, refresh,
rate limiting, unknown send handling, execute-time suppression, member offboarding,
reply body minimisation/correlation/deduplication, Calendar privacy/recurrence/
cancellation/stale updates and explicit Interaction linkage. Generic Action/Campaign,
retention/deletion and PostgreSQL RLS suites cover shared provider-neutral behaviour.
Engineering review additionally narrowed Calendar authority to the seller-owned-event
scope, excluded descriptions/attachments at the Google response boundary, made
disappearing Gmail items cursor-safe, bounded reply-operation lookup, redacted deleted
event tombstones and shared the Microsoft/Google PKCE-state lifecycle.

Visual QA used the real Settings route with synthetic API fixtures. Desktop review
covered the connected card; the current consent copy, accessible dialog and focus
return were rechecked in component tests. The 390 px review covered reauthorisation,
focus handling and zero horizontal overflow.

- [Connected desktop state](assets/wo-041-google-connected-desktop.png)
- [Reauthorisation at 390 px](assets/wo-041-google-reauthorisation-390.png)

Final local validation:

- web format, lint, strict typecheck and production build: passed;
- Vitest: 265 passed;
- Playwright: 73 passed;
- API format, Ruff, strict mypy and package build: passed;
- pytest: 1,222 passed and seven PostgreSQL-only cases skipped in the ordinary
  environment;
- fresh disposable PostgreSQL zero-to-head, drift check, downgrade/re-upgrade and
  the explicit PostgreSQL selection: passed (eight tests, 31 deselected);
- repository audit, prohibited-scope/secret review and `git diff --check`: passed.

See [Google Workspace sales integration](../03-engineering/google-workspace-sales-integration.md)
and [ADR 0071](../08-decisions/0071-google-workspace-restricted-scope-incremental-integration.md).
WO-042 is not started. WO-055 remains recorded after WO-053 and before WO-054/WO-045
and is not implemented.
