# Create security, privacy and abuse review

- **Status:** implemented WO-032 controls; target-environment launch approval remains separate
- **Data class:** confidential organisation templates, customer-safe presentation context and generated PPTX

## Trust boundary

A PPTX is an untrusted ZIP/XML package even when an administrator supplied it. The
browser sends it only to the API with exact MIME, SHA-256 checksum and a versioned
authority attestation. The server is authoritative for entitlement, role, limits,
validation, approval, source access and download. It never trusts an organisation ID,
template policy or approval state supplied by the browser.

Every Create row is organisation-owned, every relationship is tenant-composite, every
repository query includes an organisation predicate, and migration `0041_create_studio`
enables and forces PostgreSQL RLS. Administrators alone upload, classify and approve
templates; members may use approved versions. Cross-tenant identifiers return safe
not-found responses.

## Hostile-file controls

The bounded processor rejects malformed ZIPs, unsafe or duplicate paths, encrypted
entries, unsupported compression, entry/expanded/XML/media/character exhaustion,
external relationships, DTD/entities, macros, ActiveX, OLE/embedded packages,
embedded fonts, custom XML, SVG and unknown media signatures. It never invokes Office,
LibreOffice, scripts, URLs or embedded objects. Hidden slides cannot be approved;
notes/comments are warned and stripped; internal-only and pricing-placeholder content
cannot enter the approved library.

The implementation is a strict parser and renderer, not an antivirus claim. A future
target deployment may insert an approved malware scanner before storage. That does
not relax any current parser control.

## Customer-safe context and prompt-injection boundary

`customer_safe_presentation_context_v1` constructs new typed dictionaries from an
allow-list. It does not pass ORM rows or accept arbitrary model-selected fields.
Allowed sources are approved company content, current customer-direct Evidence,
clearly labelled seller-reported Evidence and separately labelled current public
Prospect observations. Focus instructions may prioritise known slide categories but
cannot add source content or override policy.

Raw transcripts, recordings, meeting notes, Opportunity value/currency, probability,
forecast, methodology score, manager coaching, internal risk, contactability,
suppression and private notes are denied. Instruction-like source text remains data;
the current deterministic composer makes no provider call. Internal-only lexical
validation runs again on edits and before output.

## Provenance, approval and download

Each material block has an exact claim manifest with origin, support, source IDs and
labels, freshness, customer-safety classification, paraphrase/exact-text policy and
review state. Seller-edited and inferred claims require keep/remove review. Approval
revalidates referenced sources and fails if a content item was withdrawn or Evidence/
public research is no longer available. Any edit creates a new unapproved version.

Source and output objects use opaque tenant-prefixed private-storage keys. Downloads
require a short-lived signed grant, current membership, current approved version and
private/no-store response headers. Keys, grants, binaries, customer text, template
text and full manifests stay out of logs and audit events; events contain safe IDs,
states, counts, versions and failure codes only.

## Residual risks and launch gates

- Structured review is not a pixel-perfect Office renderer; source-template layout
  quality and accessibility remain administrator responsibilities.
- The repository local-storage adapter is development/test only. Production requires
  private S3-compatible storage, deployment-managed secrets and verified backup,
  restore, monitoring and incident procedures.
- No production AI provider is used by Create. Adding one requires a separate data-
  flow, prompt-injection, privacy, quality, cost and residency review.
- Do not use production customer data until the repository-wide target-environment
  identity, privacy, operations and legal launch gates are satisfied.

## Abuse and regression tests

Coverage includes unsafe paths, decompression/resource ceilings, external links,
entities, macros/ActiveX/OLE/fonts/SVG, hidden slides and notes, selected-slide-only
output, metadata sanitisation, internal-content edits, exact claim review, immutable
approval, entitlement, member/admin permissions, cross-tenant access, private
download, object deletion and forced-RLS migration checks.
