# Document Evidence guide

## Current capability

WO-019 lets an authenticated organisation member deliberately add one PDF or
UTF-8 TXT document to an account, opportunity and optionally an Interaction. The
supported classifications are proposal, RFP, RFQ, requirements, contract, SOW,
pricing, procurement, security questionnaire, implementation plan, technical
specification, customer presentation, sales material and other.

The user must state whether the document is customer-provided,
salesperson-provided, jointly created, externally generated, system imported or
unknown. They must also confirm authority to use the document and acknowledge
external AI processing before upload. These declarations are provenance, not proof
of customer agreement or legal effect.

DOCX, OCR, image-only PDFs, archive files, embedded attachments, drive sync and
provider imports are not supported.

## Lifecycle

1. The browser validates the extension and 15 MB limit, calculates SHA-256 and
   sends the document through the API.
2. The API revalidates size, checksum, filename, media type, association scope,
   daily and organisation storage quotas, and parses the document before storing
   it in private object storage.
3. Processing creates page/paragraph fragments and AI-inferred candidate evidence
   with exact source locations. A deterministic no-network provider is the local
   and test default.
4. The seller edits, accepts or rejects every finding. No candidate reaches the
   Opportunity Workspace or Revenue Brain before review is complete.
5. Accepted findings create immutable evidence references and an immutable Revenue
   Brain source snapshot. Deletion removes the object before its derived lineage.

Processing may be retried up to
`API_PRIVATE_BETA_DOCUMENT_PROCESSING_RETRIES`. Idempotency keys protect request
retries; organisation-scoped checksums reject duplicate documents.

## API

- `GET /api/v1/evidence/capabilities`
- `POST /api/v1/evidence/documents`
- `GET /api/v1/evidence/documents/{document_id}`
- `GET /api/v1/evidence/documents/{document_id}/content`
- `POST /api/v1/evidence/documents/{document_id}/process`
- `POST /api/v1/evidence/documents/{document_id}/review`
- `DELETE /api/v1/evidence/documents/{document_id}`

The content endpoint verifies the tenant and a short-lived signed grant, returns
private bytes with `Cache-Control: private, no-store` and does not expose storage
keys. Metadata responses never contain extracted or raw document text.

## Provenance and interpretation

A customer-provided document can directly support a reviewed statement. A seller-
provided proposal is always `seller_prepared` and `context`; it cannot by itself
establish customer intent, acceptance or approved budget. Joint and external
sources remain reported/contextual. AI is always recorded as the interpretation
origin, independently from who created the source.

Contract and SOW extraction is operational evidence only. RevenueOS does not give
legal advice or decide whether terms are binding.

## Operations

The feature is disabled with `API_FEATURE_DOCUMENT_EVIDENCE_ENABLED=false`. Limits
are configured by `API_PRIVATE_BETA_MAX_DOCUMENT_BYTES`,
`API_PRIVATE_BETA_MAX_DOCUMENT_PAGES`,
`API_PRIVATE_BETA_MAX_DOCUMENT_TEXT_CHARACTERS`,
`API_PRIVATE_BETA_MAX_DOCUMENT_UPLOADS_PER_DAY` and
`API_PRIVATE_BETA_MAX_DOCUMENT_BYTES_PER_ORGANISATION`.

Operational events contain identifiers, type, byte count, state and safe error
codes only. They never contain filenames beyond the source record, document text,
prompts or provider payloads. See the [document parsing and security
guide](document-parsing-security-guide.md) and [private-beta
runbooks](private-beta-runbooks.md).
