# Engage outreach security, privacy and abuse review

## Decision

WO-029 is suitable for private-beta deterministic simulation. Production email
sending remains unavailable. The server fails closed rather than treating a mock,
configured OAuth client ID or UI label as a working mailbox integration.

## Assets and trust boundaries

Sensitive assets are Contact addresses, exact subject/body, source excerpts,
suppression status, future OAuth credentials and provider receipts. The browser is
untrusted. Organisation/sender/recipient/policy/version values are resolved or
revalidated by the API. The database runtime role remains tenant-scoped and must not
bypass RLS.

## Principal risks and controls

| Risk                               | Control                                                                                                         |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Cross-tenant access                | explicit organisation predicates, composite tenant FKs, forced RLS and uniform 404s                             |
| Arbitrary recipient                | public operations accept only canonical Contact/outreach IDs; exact email is server-resolved                    |
| Sender spoofing/cross-user mailbox | sender pinned to authenticated user; active connection must be created by that user                             |
| Approval used as execution         | distinct approve, preview and confirm routes; approval audit says no execution                                  |
| Stale or changed content           | immutable revisions, approved/current equality, exact fingerprint and seller-context snapshot revalidation      |
| Duplicate email                    | execution unique/idempotency boundary; repeated confirmation returns one execution                              |
| Suppression race                   | checked at draft context, approval, preview, confirmation and worker                                            |
| Contact deletion/reimport          | organisation-scoped HMAC suppression survives Contact link deletion                                             |
| Opt-out downgrade                  | active recipient/provider suppressions cannot be replaced by a reversible manual reason                         |
| Plain-address disclosure           | no address in suppression identity/log/audit metadata; key from deployment secrets                              |
| Sensitive/manipulative copy        | research category/term exclusion plus final copy validator                                                      |
| Fabricated citation                | sources selected server-side from current tenant research; no source-ID input contract                          |
| Inferred address send              | only verified/provider-supplied current Contact field is usable                                                 |
| Provider ambiguity                 | no production adapter; future boundary requires receipt/reconciliation and no blind retry                       |
| Credential leakage                 | no mailbox credentials exist; future credentials must use the established encrypted server-only store           |
| Mock in production                 | feature/provider checks reject Mock Email in production                                                         |
| Spam/bulk abuse                    | canonical Contact, single-recipient contract, entitlement, policy, cooldown and daily quotas; no list/batch API |
| Customer-truth pollution           | outbound seller activity never creates Evidence or methodology/revenue-brain confirmation                       |

## Privacy and professional-person safety

Automatic source use is limited to public professional/company context with a
supporting source and approved trust state. Religion, politics, health, sexuality,
ethnicity, disability, family/children/home, personal travel, personality and
persuasion vulnerability are not permitted personalisation inputs. The implementation
contains no personality profile, protected-trait inference or manipulation score.

Address verification and provider supply are provenance, not permission. Policy copy
explicitly assigns legal/privacy responsibility to the organisation. RevenueOS does
not silently listen, record, scrape, infer addresses or enrich from private sources.

## OAuth and provider boundary

No mailbox OAuth endpoint, callback, token or scope exists in WO-029. A future
implementation must use provider OAuth authorisation code with state and PKCE where
supported, exact redirect allowlists, least send-only scopes, server-side encrypted
tokens, key-rotation/re-auth handling, verified mailbox identity, revocation and no
token/content logging. Shared/send-as mailboxes remain out of scope until provider
permission can be proven.

## Logging, export and deletion

Structured logs/audits include IDs, controlled codes, version, purpose, source count
and execution mode only. They exclude email, subject, body, personalisation excerpt,
token and raw provider response. Export intentionally contains customer-owned
outreach content and source references but no credentials/key. Contact deletion does
not imply unsend; organisation deletion cannot recall already external email.

## Residual risk and release gate

An organisation can still configure a policy incorrectly or write inappropriate
copy manually. Mandatory human review, server copy checks, suppression and low
private-beta quotas reduce but do not eliminate legal/reputation risk. Production
email must remain disabled until one provider-specific security/reconciliation
assessment, scanner-safe opt-out where required, operational monitoring and legal
review are approved. No paid provider/service was activated for WO-029.
