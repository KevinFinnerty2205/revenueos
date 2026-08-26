# Mailbox provider evaluation for one-to-one outreach

- **Assessment date:** 26 August 2026
- **WO-029 decision:** defer a production provider; retain a provider-neutral,
  user-bound send contract and deterministic non-production simulation

## Requirements

The first provider must send as the authenticated salesperson, prove the exact
authorised mailbox identity, support least-privilege OAuth, return a durable provider
receipt/message identifier, document ambiguous outcomes and rate limits, allow safe
revocation/re-auth, and support a credible opt-out/bounce/complaint path. It must not
require broad inbox ingestion merely to send one reviewed email. Provider acceptance
must not be mislabelled as delivery.

Transactional email services were rejected for this decision because sending from a
vendor/domain is not equivalent to sending from the salesperson's authorised
mailbox. Arbitrary SMTP and implementing both ecosystems are outside WO-029.

## Google Workspace / Gmail API

Gmail exposes `users.messages.send` and accepts an RFC 2822 message. Google's scope
catalogue includes `gmail.send`, a sensitive send-only scope, while broader scopes
such as `gmail.compose` and `mail.google.com` grant more access. Google's web-server
OAuth flow documents redirect URI controls, state, offline access and refresh-token
handling.

Official references:

- [Gmail users.messages.send](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send)
- [Gmail OAuth scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Google web-server OAuth flow](https://developers.google.com/identity/protocols/oauth2/web-server)

Strengths are a focused send endpoint and a least-privilege send-only scope. Open
questions for a release include Workspace/customer mix, Google OAuth verification
and sensitive-scope operational requirements, authorised aliases/send-as discovery,
sent-message reconciliation without expanding scopes, list-unsubscribe behaviour,
bounce/reply event architecture and support ownership.

## Microsoft 365 / Microsoft Graph

Graph exposes `POST /me/sendMail`; the documented success response is `202 Accepted`
and the operation does not include the created message in the response. Delegated
`Mail.Send` permits sending as the signed-in user and does not require broad inbox
read permission. Microsoft's authorisation-code flow supports PKCE and standard
refresh-token handling.

Official references:

- [Microsoft Graph sendMail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Microsoft identity authorisation-code flow with PKCE](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)

Strengths are delegated send-only permission and common enterprise adoption.
Important unresolved work includes tenant-consent expectations, mailbox/alias/send-as
verification, reconciling `202 Accepted` without broad read scopes, Exchange
throttling, bounce/reply event semantics, shared mailbox security and support burden.

## Decision

Neither provider is selected in WO-029. The repository contains no evidence that the
private-beta design partners predominantly use one ecosystem, no approved OAuth app
registration/redirect domains, no production token-encryption operational key for a
mailbox connector, and no accepted bounce/complaint/opt-out runbook. Choosing now
would create security and operational commitments without user evidence.

The decision is therefore:

- keep `send_email` provider-neutral and pinned to the authenticated user;
- expose exact sender/recipient/content preview through the current Action/Execution
  boundary;
- permit only clearly labelled Mock Email simulation outside production;
- fail closed for production mailbox discovery and execution;
- activate no paid provider/service; and
- select at most one first provider in a later approved work order after design-
  partner stack evidence and a provider-specific security/reconciliation review.

This is not an implementation of Gmail, Outlook or mailbox OAuth. Environment
variables or UI copy alone must never be described as a working connection.

## Future adapter contract

A selected adapter must accept the exact approved Action payload plus server-bound
connection identity. It may add a stable client marker/header only where the provider
documents support. It returns controlled accepted/provider-reference state, never raw
provider payload. Safe pre-acceptance failures may use bounded retry with
`Retry-After`; timeouts after possible acceptance enter unknown delivery and require
provider-specific reconciliation. No automatic blind resend is allowed.

Inbound full-mailbox sync, tracking pixels, click redirects, shared mailboxes,
arbitrary aliases and dual-provider implementation remain separate decisions.
