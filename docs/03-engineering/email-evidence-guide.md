# Email Evidence guide

## Current capability

WO-019 accepts deliberately pasted plain-text email evidence. A user selects an
account or opportunity, message time, source type and direction, then confirms
authority and external AI processing. An Interaction is optional.

Supported source types are customer-sent, salesperson-sent, internal forward and
manually pasted. `external_provider_import` exists as a future contract value but
cannot be created by the current public workflow. Directions are inbound,
outbound, internal and unknown.

There is no Gmail, Outlook, mailbox, calendar or background synchronisation. The
system does not auto-create or fuzzy-match Contacts. Only an exact existing Contact
in the same tenant and account may verify an inbound customer sender.

## Lifecycle

1. The browser submits a plain-text subject/body and explicit provenance fields.
2. The API validates tenant-scoped relationships, limits and a content checksum,
   then conservatively normalises unambiguous signatures and quoted reply blocks.
3. Processing generates AI-inferred candidate evidence with line locations.
4. The user must edit, accept or reject every candidate; a zero-finding result is
   also explicitly completed.
5. Only accepted findings create immutable evidence and Revenue Brain source
   snapshots.

Idempotency keys protect retries. Organisation-scoped content hashes prevent the
same pasted message being added repeatedly. Processing retries are bounded by
`API_PRIVATE_BETA_EMAIL_PROCESSING_RETRIES`.

## API

- `POST /api/v1/evidence/emails`
- `GET /api/v1/evidence/emails/{email_id}`
- `POST /api/v1/evidence/emails/{email_id}/process`
- `POST /api/v1/evidence/emails/{email_id}/review`
- `DELETE /api/v1/evidence/emails/{email_id}`

Responses expose metadata, provenance and review candidates but never the raw or
normalised body. Deletion clears both bodies and the subject and removes all
candidate, accepted-evidence and Revenue Brain lineage.

## Trust rules

Only a `customer_sent` inbound message tied to an exact tenant/account Contact is
`customer_direct` and `direct`. Outbound or internal messages remain
`salesperson_reported` and `context`; manually pasted messages without verified
identity are imported/reported. The direction and label are never inferred from
body text.

The source author and AI interpretation are separate dimensions. Seller-written
text cannot become customer-confirmed intent, budget or acceptance merely because
the model extracted a sentence from it.

## Operations

Disable the path with `API_FEATURE_EMAIL_EVIDENCE_ENABLED=false`. The daily
analysis limit is `API_PRIVATE_BETA_MAX_EMAIL_ANALYSES_PER_DAY`; plain-text bodies
are capped server-side.
Logs and operational events contain IDs, direction, state, counts and safe error
codes only—not subjects, bodies, prompts or addresses. See [email sanitisation and
security](email-sanitisation-security-guide.md) and [document/email
provenance](document-email-provenance.md).
